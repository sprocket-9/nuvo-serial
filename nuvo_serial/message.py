from __future__ import annotations

from dataclasses import dataclass
from enum import Flag, auto, unique
import logging
import re
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Literal,
    Optional,
    Match,
    Tuple,
    Type,
    Union,
    List,
)

from nuvo_serial.const import (
    MODEL_GC,
    MODEL_ESSENTIA_G,
    ERROR_RESPONSE,
    OK_RESPONSE,
    ZONE_ALL_OFF,
    ZONE_BUTTON,
    ZONE_CONFIGURATION,
    SYSTEM_PARTY,
    ZONE_VOLUME_CONFIGURATION,
    ZONE_EQ_STATUS,
    ZONE_STATUS,
    SOURCE_CONFIGURATION,
    SYSTEM_MUTE,
    SYSTEM_PAGING,
    SYSTEM_VERSION,
    SYSTEM_RESTART,

)
from nuvo_serial.exceptions import (
    MessageClassificationError,
    MessageFormatError,
    MessageResponseError,
)

from nuvo_serial.nuvo_typing import (
    NuvoMsgType
)

_LOGGER = logging.getLogger(__name__)

CONCERTO_VERSION_PATTERN = re.compile(
    r"#VER\"(?P<product_number>.+)?\s+(?P<fw_version>.+)?\s+(?P<hw_version>.+)?\""
)

CONCERTO_ZONE_ON_PATTERN = re.compile(
    r"Z(?P<zone>\d+),"
    r"(?P<power>ON|OFF),"
    r"SRC(?P<source>\d+),"
    r"(VOL)?(?P<volume>\d+|MUTE),"
    r"DND(?P<dnd>0|1),"
    r"LOCK(?P<lock>0|1)"
)

CONCERTO_ZONE_OFF_PATTERN = re.compile(r"#Z(?P<zone>\d+)," r"(?P<power>OFF)")

CONCERTO_ZONE_EQ_PATTERN = re.compile(
    r"#ZCFG(?P<zone>\d+),"
    r"BASS(?P<bass>-?\d+),"
    r"TREB(?P<treble>-?\d+),"
    r"BAL(?P<balance_position>L|R|C)(?P<balance>\d+)?,"
    r"LOUDCMP(?P<loudcmp>0|1)"
)

CONCERTO_ZONE_CONFIGURATION_DISABLED_PATTERN = re.compile(
    r"#ZCFG(?P<zone>\d+)," r"ENABLE(?P<enabled>0)"
)

CONCERTO_ZONE_CONFIGURATION_ENABLED_PATTERN = re.compile(
    r"#ZCFG(?P<zone>\d+),"
    r"ENABLE(?P<enabled>0|1),"
    r"NAME\"(?P<name>.+)?\","
    r"SLAVETO(?P<slave_to>\d+),"
    r"GROUP(?P<group>\d),"
    r"SOURCES(?P<sources>\d+),"
    r"XSRC(?P<xsrc>0|1),"
    r"IR(?P<ir>\d),"
    r"DND(?P<dnd>\d),"
    r"LOCKED(?P<locked>0|1),"
    r"SLAVEEQ(?P<slave_eq>\d)"
)

CONCERTO_SOURCE_CONFIGURATION_DISABLED_PATTERN = re.compile(
    r"#SCFG(?P<source>\d)," r"ENABLE(?P<enabled>0)"
)
CONCERTO_SOURCE_CONFIGURATION_ENABLED_PATTERN = re.compile(
    r"#SCFG(?P<source>\d),"
    r"ENABLE(?P<enabled>0|1),"
    r"NAME\"(?P<name>.+)?\","
    r"GAIN(?P<gain>\d+),"
    r"NUVONET(?P<nuvonet_source>0|1),"
    r"SHORTNAME\"(?P<short_name>.+)?\""
    # SRCSTATUS(?P<source_status>\d),\  # In spec document but missing in reply
)

CONCERTO_ZONE_VOLUME_CONFIGURATION_PATTERN = re.compile(
    r"#ZCFG(?P<zone>\d+),"
    r"(MAXVOL)?(?P<max_vol>\d+),"
    r"(INIVOL)?(?P<ini_vol>\d+),"
    r"(PAGEVOL)?(?P<page_vol>\d+),"
    r"(PARTYVOL)?(?P<party_vol>\d+),"
    r"VOLRST(?P<vol_rst>0|1)$"
)

CONCERTO_ZONE_BUTTON_PATTERN = re.compile(
    r"#Z(?P<zone>\d+)S(?P<source>\d)(?P<button>PLAYPAUSE|PREV|NEXT)$"
)

CONCERTO_ZONE_ALL_OFF = re.compile(
    r"#ALLOFF$"
)

CONCERTO_MUTE_RESPONSE = re.compile(
    r"#MUTE(?P<mute>0|1)$"
)

CONCERTO_ERROR_RESPONSE = re.compile(
    r"#\?$"
)
CONCERTO_OK_RESPONSE = re.compile(
    r"#OK$"
)

CONCERTO_PAGE_RESPONSE = re.compile(r"#PAGE(?P<page>0|1)$")

CONCERTO_PARTY_RESPONSE = re.compile(r"#Z(?P<zone>\d+),PARTY(?P<party_host>0|1)$")

CONCERTO_RESTART_RESPONSE = re.compile(r"\x00\x00#RESTART.+$")


class FlagHelper(Flag):
    def to_list(self) -> List[Optional[str]]:
        """
        With current Flag implementation can't see an easy way to iterate
        through a Flag instance to see which flags are set  but using the 'in' operator
        does seem to work on an instance, so adding this method to iterate through
        the class members and check if they're present in the instance.
        Looks like there are some changes coming in python 3.10 to address
        this: https://bugs.python.org/issue38250
        """
        klass = type(self)
        list_of_names = []
        for name, member in klass.__members__.items():
            if member in self:
                list_of_names.append(member.name)
        return list_of_names


@unique
class SourceMask(FlagHelper, Flag):
    """
    Mask for sources a zone is allowed to select
    Can create an instance reflecting a zone's allowed sources using either:
    sm = SourceMask(17) # Sources 1 and 5
    sm = SourceMask['SOURCE1'] | SourceMask['SOURCE5']
    sm = SourceMask.SOURCE1 | SourceMask.SOURCE5
    """

    SOURCE1 = auto()
    SOURCE2 = auto()
    SOURCE3 = auto()
    SOURCE4 = auto()
    SOURCE5 = auto()
    SOURCE6 = auto()


@unique
class DndMask(FlagHelper, Flag):
    """
    Mask for a zone's DND setting
    """

    NOMUTE = auto()
    NOPAGE = auto()
    NOPARTY = auto()


@dataclass
class Party:
    zone: int
    party_host: bool

    @classmethod
    def _parse_response(cls, response_string: str) -> Optional[Match[str]]:
        return re.search(CONCERTO_PARTY_RESPONSE, response_string)

    @classmethod
    def from_string(cls, response_string: Optional[str]) -> Optional[Party]:
        if not response_string:
            return None

        match = cls._parse_response(response_string)

        if not match:
            return None

        return Party(
            zone=int(match.group("zone")),
            party_host=bool(int(match.group("party_host")))
        )


@dataclass
class Paging:
    page: bool

    @classmethod
    def _parse_response(cls, response_string: str) -> Optional[Match[str]]:
        return re.search(CONCERTO_PAGE_RESPONSE, response_string)

    @classmethod
    def from_string(cls, response_string: Optional[str]) -> Optional[Paging]:
        if not response_string:
            return None

        match = cls._parse_response(response_string)

        if not match:
            return None

        return Paging(bool(int(match.group("page"))))


@dataclass
class Mute:
    mute: bool

    @classmethod
    def _parse_response(cls, response_string: str) -> Optional[Match[str]]:
        return re.search(CONCERTO_MUTE_RESPONSE, response_string)

    @classmethod
    def from_string(cls, response_string: Optional[str]) -> Optional[Mute]:
        if not response_string:
            return None

        match = cls._parse_response(response_string)

        if not match:
            return None

        return Mute(bool(int(match.group("mute"))))


@dataclass
class Restart:

    @classmethod
    def _parse_response(cls, response_string: str) -> Optional[Match[str]]:
        return re.search(CONCERTO_RESTART_RESPONSE, response_string)

    @classmethod
    def from_string(cls, response_string: Optional[str]) -> Optional[Restart]:
        if not response_string:
            return None

        match = cls._parse_response(response_string)

        if not match:
            return None

        return Restart()


@dataclass
class ErrorResponse:
    error_response: bool

    @classmethod
    def _parse_response(cls, response_string: str) -> Optional[Match[str]]:
        return re.search(CONCERTO_ERROR_RESPONSE, response_string)

    @classmethod
    def from_string(cls, response_string: Optional[str]) -> Optional[ErrorResponse]:
        if not response_string:
            return None

        match = cls._parse_response(response_string)

        if not match:
            return None

        return ErrorResponse(error_response=True)


@dataclass
class OKResponse:
    ok_response: bool

    @classmethod
    def _parse_response(cls, response_string: str) -> Optional[Match[str]]:
        return re.search(CONCERTO_OK_RESPONSE, response_string)

    @classmethod
    def from_string(cls, response_string: Optional[str]) -> Optional[OKResponse]:
        if not response_string:
            return None

        match = cls._parse_response(response_string)

        if not match:
            return None

        return OKResponse(ok_response=True)


@dataclass
class ZoneAllOff:
    all_off: bool

    @classmethod
    def _parse_response(cls, response_string: str) -> Optional[Match[str]]:
        return re.search(CONCERTO_ZONE_ALL_OFF, response_string)

    @classmethod
    def from_string(cls, response_string: Optional[str]) -> Optional[ZoneAllOff]:
        if not response_string:
            return None

        match = cls._parse_response(response_string)

        if not match:
            return None

        return ZoneAllOff(all_off=True)


@dataclass
class Version:
    model: str
    product_number: str
    firmware_version: str
    hardware_version: str

    models = {"NV-I8G": MODEL_GC, "NV-E6G": MODEL_ESSENTIA_G}

    @classmethod
    def _parse_response(cls, response_string: str) -> Optional[Match[str]]:
        return re.search(CONCERTO_VERSION_PATTERN, response_string)

    @classmethod
    def from_string(cls, response_string: Optional[str]) -> Optional[Version]:
        if not response_string:
            return None

        version_values = cls._parse_response(response_string)

        if not version_values:
            return None

        product_number = version_values.group("product_number")
        model = cls.models.get(product_number, "unknown_model")
        firmware_version = version_values.group("fw_version")
        hardware_version = version_values.group("hw_version")

        return Version(model, product_number, firmware_version, hardware_version)


@dataclass
class ZoneStatus:
    zone: int
    power: bool
    source: Optional[int] = None
    volume: Optional[int] = None
    mute: Optional[bool] = None
    dnd: Optional[bool] = None
    lock: Optional[bool] = None

    @classmethod
    def _parse_response(cls, response_string: str) -> Optional[Match[str]]:
        found_match = None
        match = re.search(CONCERTO_ZONE_ON_PATTERN, response_string)

        if match:
            _LOGGER.debug("CONCERTO_ZONE_ON_PATTERN - Match")
            found_match = match
        else:
            match = re.search(CONCERTO_ZONE_OFF_PATTERN, response_string)
            if match:
                _LOGGER.debug("CONCERTO_ZONE_OFF_PATTERN - Match")
                found_match = match

        return found_match

    @classmethod
    def from_string(cls, response_string: Optional[str]) -> Optional[ZoneStatus]:
        if not response_string:
            return None

        zone_values = cls._parse_response(response_string)

        if not zone_values:
            return None

        z_power = False
        z_source = None
        z_volume = None
        z_dnd = None
        z_lock = None
        z_mute = None

        z_zone = int(zone_values.group("zone"))

        if zone_values.group("power") == "ON":
            z_power = True
            z_source = int(zone_values.group("source"))
            z_dnd = bool(int(zone_values.group("dnd")))
            z_lock = bool(int(zone_values.group("lock")))
            if zone_values.group("volume") == "MUTE":
                z_mute = True
            else:
                z_volume = int(zone_values.group("volume"))
                z_mute = False

        return ZoneStatus(z_zone, z_power, z_source, z_volume, z_mute, z_dnd, z_lock)


@dataclass
class ZoneEQStatus:
    zone: int
    bass: int
    treble: int
    loudcmp: bool
    balance_position: str
    balance: int

    @classmethod
    def _fix_balance_reverse_bug(cls, balance: str) -> str:
        """
        Grand Concerto bug (at least on v2.66 firmware)
        Unit reports the incorrect R/L side in its response
        This applies to the balance set and the eq status command
        Fix this by returning the reversed side
        """
        reverse = {"L": "R", "R": "L", "C": "C"}

        return reverse[balance]

    @classmethod
    def _parse_response(cls, response_string: str) -> Optional[Match[str]]:
        found_match = None
        match = re.search(CONCERTO_ZONE_EQ_PATTERN, response_string)

        if match:
            _LOGGER.debug("CONCERTO_ZONE_EQ_PATTER - Match")
            found_match = match

        return found_match

    @classmethod
    def from_string(cls, response_string: Optional[str]) -> Optional[ZoneEQStatus]:
        if not response_string:
            return None

        zone_values = cls._parse_response(response_string)

        if not zone_values:
            return None

        z_balance = 0

        z_zone = int(zone_values.group("zone"))
        z_bass = int(zone_values.group("bass"))
        z_treble = int(zone_values.group("treble"))
        z_loudcmp = bool(int(zone_values.group("loudcmp")))
        z_balance_position = cls._fix_balance_reverse_bug(
            str(zone_values.group("balance_position"))
        )

        if z_balance_position != "C":
            z_balance = int(zone_values.group("balance"))

        return ZoneEQStatus(
            z_zone, z_bass, z_treble, z_loudcmp, z_balance_position, z_balance
        )


@dataclass
class ZoneConfiguration:
    zone: int
    enabled: bool
    name: Optional[str] = None
    slave_to: Optional[int] = None
    group: Optional[int] = None
    sources: Optional[list[Optional[str]]] = None
    exclusive_source: Optional[bool] = None
    ir_enabled: Optional[int] = None
    dnd: Optional[list[Optional[str]]] = None
    locked: Optional[bool] = None
    slave_eq: Optional[bool] = None

    @classmethod
    def _parse_response(cls, response_string: str) -> Optional[Match[str]]:
        found_match = None
        match = re.search(CONCERTO_ZONE_CONFIGURATION_ENABLED_PATTERN, response_string)

        if match:
            _LOGGER.debug("CONCERTO_ZONE_CONFIGURATION_ENABLED_PATTERN - Match")
            found_match = match
        else:
            match = re.search(
                CONCERTO_ZONE_CONFIGURATION_DISABLED_PATTERN, response_string
            )
            if match:
                _LOGGER.debug("CONCERTO_ZONE_CONFIGURATION_DISABLED_PATTERN - Match")
                found_match = match

        return found_match

    @classmethod
    def from_string(cls, response_string: Optional[str]) -> Optional[ZoneConfiguration]:
        if not response_string:
            return None

        zone_values = cls._parse_response(response_string)

        if not zone_values:
            return None

        z_enabled = False
        z_name = None
        z_slave_to = None
        z_group = None
        z_sources = None
        z_exclusive_source = None
        z_ir_enabled = None
        z_dnd = None
        z_locked = None
        z_slave_eq = None

        z_zone = int(zone_values.group("zone"))
        z_enabled = bool(int(zone_values.group("enabled")))

        if z_enabled:
            z_name = zone_values.group("name")
            z_slave_to = int(zone_values.group("slave_to"))
            z_group = int(zone_values.group("group"))
            z_sources = SourceMask(int(zone_values.group("sources"))).to_list()
            z_exclusive_source = bool(int(zone_values.group("xsrc")))
            z_ir_enabled = int(zone_values.group("ir"))
            z_dnd = DndMask(int(zone_values.group("dnd"))).to_list()
            z_locked = bool(int(zone_values.group("locked")))
            z_slave_eq = bool(int(zone_values.group("slave_eq")))

        return ZoneConfiguration(
            z_zone,
            z_enabled,
            z_name,
            z_slave_to,
            z_group,
            z_sources,
            z_exclusive_source,
            z_ir_enabled,
            z_dnd,
            z_locked,
            z_slave_eq,
        )


@dataclass
class SourceConfiguration:
    source: int
    enabled: bool
    name: Optional[str]
    gain: Optional[int]
    nuvonet_source: Optional[bool]
    short_name: Optional[str]

    @classmethod
    def _parse_response(cls, response_string: str) -> Optional[Match[str]]:
        found_match = None

        match = re.search(CONCERTO_SOURCE_CONFIGURATION_ENABLED_PATTERN, response_string)

        if match:
            _LOGGER.debug("CONCERTO_SOURCE_CONFIGURATION_ENABLED_PATTERN - Match")
            found_match = match
        else:
            match = re.search(CONCERTO_SOURCE_CONFIGURATION_DISABLED_PATTERN, response_string)
            if match:
                _LOGGER.debug("CONCERTO_SOURCE_CONFIGURATION_DISABLED_PATTERN - Match")
                found_match = match

        return found_match

    @classmethod
    def from_string(
        cls, response_string: Optional[str]
    ) -> Optional[SourceConfiguration]:
        if not response_string:
            return None

        source_values = cls._parse_response(response_string)

        if not source_values:
            return None

        s_source = 0
        s_enabled = False
        s_name = None
        s_gain = None
        s_nuvonet_source = None
        s_short_name = None

        s_source = int(source_values.group("source"))
        s_enabled = bool(int(source_values.group("enabled")))

        if s_enabled:
            s_name = source_values.group("name")
            s_gain = int(source_values.group("gain"))
            s_nuvonet_source = bool(int(source_values.group("nuvonet_source")))
            s_short_name = source_values.group("short_name")

        return SourceConfiguration(
            s_source, s_enabled, s_name, s_gain, s_nuvonet_source, s_short_name,
        )


@dataclass
class ZoneVolumeConfiguration:
    zone: int
    max_vol: int
    ini_vol: int
    page_vol: int
    party_vol: int
    vol_rst: bool

    @classmethod
    def _parse_response(cls, response_string: str) -> Optional[Match[str]]:
        found_match = None
        match = re.search(CONCERTO_ZONE_VOLUME_CONFIGURATION_PATTERN, response_string)

        if match:
            _LOGGER.debug("CONCERTO_ZONE_VOLUME_CONFIGURATION_PATTERN - Match")
            found_match = match

        return found_match

    @classmethod
    def from_string(
        cls, response_string: Optional[str]
    ) -> Optional[ZoneVolumeConfiguration]:
        if not response_string:
            return None

        zone_values = cls._parse_response(response_string)

        if not zone_values:
            return None

        return ZoneVolumeConfiguration(
            int(zone_values.group("zone")),
            int(zone_values.group("max_vol")),
            int(zone_values.group("ini_vol")),
            int(zone_values.group("page_vol")),
            int(zone_values.group("party_vol")),
            bool(int(zone_values.group("vol_rst"))),
        )


@dataclass
class ZoneButton:
    zone: int
    source: int
    button: str

    @classmethod
    def _parse_response(cls, response_string: str) -> Optional[Match[str]]:
        found_match = None
        match = re.search(CONCERTO_ZONE_BUTTON_PATTERN, response_string)

        if match:
            _LOGGER.debug("CONCERTO_ZONE_BUTTON_PATTERN - Match")
            found_match = match

        return found_match

    @classmethod
    def from_string(cls, response_string: Optional[str]) -> Optional[ZoneButton]:
        if not response_string:
            return None

        button_values = cls._parse_response(response_string)

        if not button_values:
            return None

        return ZoneButton(
            int(button_values.group("zone")),
            int(button_values.group("source")),
            button_values.group("button"),
        )


NuvoClass = Union[
    ErrorResponse,
    OKResponse,
    Mute,
    Paging,
    Party,
    Restart,
    ZoneAllOff,
    ZoneStatus,
    ZoneEQStatus,
    ZoneConfiguration,
    SourceConfiguration,
    ZoneVolumeConfiguration,
    ZoneButton,
    Version,
]

MSG_CLASSES = {
    MODEL_GC: {
        ERROR_RESPONSE: ErrorResponse,
        OK_RESPONSE: OKResponse,
        ZONE_ALL_OFF: ZoneAllOff,
        ZONE_STATUS: ZoneStatus,
        ZONE_EQ_STATUS: ZoneEQStatus,
        ZONE_CONFIGURATION: ZoneConfiguration,
        SOURCE_CONFIGURATION: SourceConfiguration,
        ZONE_VOLUME_CONFIGURATION: ZoneVolumeConfiguration,
        ZONE_BUTTON: ZoneButton,
        SYSTEM_MUTE: Mute,
        SYSTEM_PARTY: Party,
        SYSTEM_PAGING: Paging,
        SYSTEM_RESTART: Restart,
        SYSTEM_VERSION: Version,
    }
}

MSG_CLASSES[MODEL_ESSENTIA_G] = MSG_CLASSES[MODEL_GC]


MSG_CLASS_KEYS = {
    OK_RESPONSE: "generic",
    ZONE_ALL_OFF: "system",
    ZONE_STATUS: "zone",
    ZONE_EQ_STATUS: "zone",
    ZONE_CONFIGURATION: "zone",
    SOURCE_CONFIGURATION: "source",
    ZONE_VOLUME_CONFIGURATION: "zone",
    ZONE_BUTTON: "zone",
    SYSTEM_MUTE: "system",
    SYSTEM_PARTY: "system",
    SYSTEM_PAGING: "system",
    SYSTEM_RESTART: "system",
    SYSTEM_VERSION: "system",
}

MSG_CLASS_TRACK = {
    MODEL_GC: [
        ZONE_STATUS,
        ZONE_EQ_STATUS,
        ZONE_CONFIGURATION,
        SOURCE_CONFIGURATION,
        SYSTEM_PARTY,
        ZONE_VOLUME_CONFIGURATION,
        SYSTEM_VERSION
    ]
}

MSG_CLASS_TRACK[MODEL_ESSENTIA_G] = MSG_CLASS_TRACK[MODEL_GC]

MSG_CLASS_QUERY_ZONE_STATUS = {
    MODEL_GC: [
        ZONE_ALL_OFF,
        SYSTEM_MUTE,
        SYSTEM_PAGING,
        SYSTEM_RESTART
    ]
}

MSG_CLASS_QUERY_ZONE_STATUS[MODEL_ESSENTIA_G] =  MSG_CLASS_QUERY_ZONE_STATUS[MODEL_GC]

def process_message(model: str, message: bytes) -> Tuple[str, NuvoClass]:
    """
    Attempt to classify the received message
    """
    _LOGGER.debug("MSGCLASSIFIER: Process received message: %s", message)
    msg = message.rstrip().decode("ascii")

    processed_type: str
    processed_data: NuvoClass
    found_match = False

    for msg_type, msg_class in MSG_CLASSES[model].items():
        d_class = msg_class.from_string(msg) # type: ignore
        if d_class:
            found_match = True
            processed_type = msg_type
            processed_data = d_class
            break

    if not found_match:
        _LOGGER.debug("MSGCLASSIFIER: Unable to classify msg: %s", msg)
        raise MessageClassificationError(msg)
    else:
        _LOGGER.debug(
            "MSGCLASSIFIER: Classified message as type %s %s",
            processed_type,
            processed_data,
        )

    return (processed_type, processed_data)


def format_message(model: str, message: str) -> bytes:
    message = f"*{message}\r"
    return message.encode("ascii")
