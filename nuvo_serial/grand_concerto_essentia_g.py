from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from dataclasses import asdict
from enum import Flag, auto, unique
import logging
import re
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Optional,
    Match,
    Type,
    TypeVar,
    Union,
    List,
)

import icontract

from nuvo_serial.connection import (
    synchronized,
    locked,
    SyncRequest,
    AsyncConnection,
    MsgBus,
)

from nuvo_serial.configuration import config

from nuvo_serial.const import (
    ZONE_ALL_OFF,
    ZONE_STATUS,
    ZONE_EQ_STATUS,
    ZONE_CONFIGURATION,
    ZONE_VOLUME_CONFIGURATION,
    SOURCE_CONFIGURATION,
    ZONE_BUTTON,
    ZONE_BUTTON_PLAY_PAUSE,
    ZONE_BUTTON_PREV,
    ZONE_BUTTON_NEXT,
    SYSTEM_VERSION,
)
from nuvo_serial.exceptions import ModelMismatchError
from nuvo_serial.message import (
    DndMask,
    SourceConfiguration,
    SourceMask,
    ZoneAllOff,
    ZoneButton,
    ZoneConfiguration,
    ZoneEQStatus,
    ZoneStatus,
    ZoneVolumeConfiguration,
    Version,
)

_LOGGER = logging.getLogger(__name__)

SOURCE_RANGE: range
SOURCE_NAME_LONG_MAX_LENGTH: int
SOURCE_NAME_SHORT_MAX_LENGTH: int
SOURCE_GAIN_RANGE: range
VOLUME_RANGE: range

ZONE_RANGE: range
ZONE_RANGE_PHYSICAL: range
ZONE_NAME_MAX_LENGTH: int
SLAVE_TO_RANGE: range
GROUP_RANGE: range
IR_STATE_RANGE: range

BASS_RANGE: range
TREBLE_RANGE: range
BALANCE_RANGE: range
BALANCE_POSITIONS: tuple[str]


def _set_model_globals(model: str) -> None:
    global SOURCE_RANGE
    SOURCE_RANGE = range(1, config[model]["sources"]["total"] + 1)

    global ZONE_RANGE
    ZONE_RANGE = range(1, config[model]["zones"]["total"] + 1)

    global ZONE_RANGE_PHYSICAL
    ZONE_RANGE_PHYSICAL = range(1, config[model]["zones"]["physical"] + 1)

    global SOURCE_NAME_LONG_MAX_LENGTH
    SOURCE_NAME_LONG_MAX_LENGTH = config[model]["sources"]["name_long_max_length"]

    global SOURCE_NAME_SHORT_MAX_LENGTH
    SOURCE_NAME_SHORT_MAX_LENGTH = config[model]["sources"]["name_short_max_length"]

    global SOURCE_GAIN_RANGE
    SOURCE_GAIN_RANGE = range(
        config[model]["gain"]["min"],
        config[model]["gain"]["max"] + 1,
        config[model]["gain"]["step"],
    )

    global VOLUME_RANGE
    VOLUME_RANGE = range(
        config[model]["volume"]["max"],
        config[model]["volume"]["min"] + 1,
        config[model]["volume"]["step"],
    )

    global ZONE_NAME_MAX_LENGTH
    ZONE_NAME_MAX_LENGTH = config[model]["zones"]["name_max_length"]

    global BASS_RANGE
    BASS_RANGE = range(
        config[model]["bass"]["min"],
        config[model]["bass"]["max"] + 1,
        config[model]["bass"]["step"],
    )

    global TREBLE_RANGE
    TREBLE_RANGE = range(
        config[model]["treble"]["min"],
        config[model]["treble"]["max"] + 1,
        config[model]["treble"]["step"],
    )

    global BALANCE_RANGE
    BALANCE_RANGE = range(
        config[model]["balance"]["min"],
        config[model]["balance"]["max"] + 1,
        config[model]["balance"]["step"],
    )

    global BALANCE_POSITIONS
    BALANCE_POSITIONS = config[model]["balance"]["positions"]


class NuvoAsync:
    def __init__(
        self,
        port_url: str,
        model: str,
        timeout: Optional[float] = None,
        disconnect_time: Optional[float] = None,
        do_model_check: Optional[bool] = True,
    ):
        self._retry_request = None
        self._port_url = port_url
        self._model = model
        self._timeout = timeout
        self._disconnect_time = disconnect_time
        self._do_model_check = do_model_check
        _set_model_globals(self._model)
        self._bus = MsgBus()
        self._physical_zones: int = config[self._model]["zones"]["physical"]

    async def connect(self) -> None:
        _LOGGER.info('Attempting connection to "%s"', self._port_url)
        self._connection = AsyncConnection(
            self._port_url, self._model, self._bus, self._timeout, self._disconnect_time
        )

        await self._connection.connect()

        if self._do_model_check:
            try:
                """
                Attempt to retrieve version information to confirm there is a working
                connection
                """
                version = await self.get_version()
            except Exception:
                await self.disconnect()
                raise

            if version.model != self._model:
                await self.disconnect()
                raise ModelMismatchError(
                    f"Specified model {self._model}, reported model: {version}"
                )

    async def disconnect(self) -> None:
        _LOGGER.debug("Requesting disconnect")
        await self._connection.disconnect()
        _LOGGER.debug("Disconnect completed")

    def add_subscriber(self, coro: Callable[..., Coroutine], event_name: str) -> None:
        self._bus.add_subscriber(coro, event_name)

    def remove_subscriber(
        self, coro: Callable[..., Coroutine], event_name: str
    ) -> None:
        self._bus.remove_subscriber(coro, event_name)

    async def _get_zone_states(self) -> None:
        for zone in ZONE_RANGE_PHYSICAL:
            await self.zone_status(zone)

    """
    Zone Status Commands
    """

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    async def zone_status(self, zone: int) -> ZoneStatus:
        return await self._connection.send_message(
            _format_zone_status_request(zone), ZONE_STATUS
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    async def set_power(self, zone: int, power: bool) -> ZoneStatus:
        return await self._connection.send_message(
            _format_set_power(zone, power), ZONE_STATUS
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    async def set_mute(self, zone: int, mute: bool) -> ZoneStatus:
        return await self._connection.send_message(
            _format_set_mute(zone, mute), ZONE_STATUS
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda volume: volume in VOLUME_RANGE)
    async def set_volume(self, zone: int, volume: int) -> ZoneStatus:
        return await self._connection.send_message(
            _format_set_volume(zone, volume), ZONE_STATUS
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda source: source in SOURCE_RANGE)
    async def set_source(self, zone: int, source: int) -> ZoneStatus:
        return await self._connection.send_message(
            _format_set_source(zone, source), ZONE_STATUS
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    async def set_next_source(self, zone: int) -> ZoneStatus:
        return await self._connection.send_message(
            _format_set_next_source(zone), ZONE_STATUS
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    async def set_dnd(self, zone: int, dnd: bool) -> ZoneStatus:
        return await self._connection.send_message(
            _format_set_dnd(zone, dnd), ZONE_STATUS
        )

    async def restore_zone(self, status: ZoneStatus) -> ZoneStatus:
        await self.set_power(status.zone, status.power)
        await self.set_mute(status.zone, status.mute)
        await self.set_volume(status.zone, status.volume)
        z_status: ZoneStatus = await self.set_source(status.zone, status.source)
        return z_status

    """
    Zone Configuration Commands
    """

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    async def zone_configuration(self, zone: int) -> ZoneConfiguration:
        return await self._connection.send_message(
            _format_zone_configuration_request(zone), ZONE_CONFIGURATION
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(
        lambda sources: not len(sources)
        or all([src in SourceMask.__members__.keys() for src in sources])
    )
    async def zone_set_source_mask(
        self, zone: int, sources: List[str]
    ) -> ZoneConfiguration:
        """
        sources: [] to disallow all sources or ['SOURCE1', 'SOURCE3'...]
        """
        mask = SourceMask(0)
        for source in sources:
            mask = mask | SourceMask[source]

        return await self._connection.send_message(
            _format_zone_set_source_mask(zone, mask.value), ZONE_CONFIGURATION,
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(
        lambda dnd: not len(dnd)
        or all([option in DndMask.__members__.keys() for option in dnd])
    )
    async def zone_set_dnd_mask(self, zone: int, dnd: List[str]) -> ZoneConfiguration:
        """
       dnd: [] to clear all DND options or a combo of ['NOMUTE', 'NOPAGE', 'NOPARTY']
        """
        mask = DndMask(0)
        for option in dnd:
            mask = mask | DndMask[option]

        return await self._connection.send_message(
            _format_zone_set_dnd_mask(zone, mask.value), ZONE_CONFIGURATION,
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda name: len(name) <= ZONE_NAME_MAX_LENGTH)
    async def zone_set_name(self, zone: int, name: str) -> ZoneConfiguration:
        return await self._connection.send_message(
            _format_zone_set_name(zone, name), ZONE_CONFIGURATION,
        )

    """
    Source Configuration Commands
    """

    @locked
    @icontract.require(lambda source: source in SOURCE_RANGE)
    async def source_status(self, source: int) -> SourceConfiguration:
        return await self._connection.send_message(
            _format_source_status_request(source), SOURCE_CONFIGURATION
        )

    @locked
    @icontract.require(lambda source: source in SOURCE_RANGE)
    @icontract.require(lambda gain: gain in SOURCE_GAIN_RANGE)
    async def set_source_gain(self, source: int, gain: int) -> SourceConfiguration:
        return await self._connection.send_message(
            _format_set_source_gain(source, gain), SOURCE_CONFIGURATION
        )

    @locked
    @icontract.require(lambda source: source in SOURCE_RANGE)
    @icontract.require(lambda name: len(name) <= SOURCE_NAME_LONG_MAX_LENGTH)
    async def set_source_name(self, source: int, name: str) -> SourceConfiguration:
        return await self._connection.send_message(
            _format_set_source_name(source, name), SOURCE_CONFIGURATION
        )

    @locked
    @icontract.require(lambda source: source in SOURCE_RANGE)
    async def set_source_enable(self, source: int, enable: bool) -> SourceConfiguration:
        return await self._connection.send_message(
            _format_set_source_enable(source, enable), SOURCE_CONFIGURATION
        )

    @locked
    @icontract.require(lambda source: source in SOURCE_RANGE)
    async def set_source_nuvonet(
        self, source: int, nuvonet: bool
    ) -> SourceConfiguration:
        return await self._connection.send_message(
            _format_set_source_nuvonet(source, nuvonet), SOURCE_CONFIGURATION
        )

    @locked
    @icontract.require(lambda source: source in SOURCE_RANGE)
    @icontract.require(lambda shortname: len(shortname) <= SOURCE_NAME_SHORT_MAX_LENGTH)
    async def set_source_shortname(
        self, source: int, shortname: str
    ) -> SourceConfiguration:
        return await self._connection.send_message(
            _format_set_source_shortname(source, shortname), SOURCE_CONFIGURATION
        )

    """
    Zone EQ Status Commands
    """

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    async def zone_eq_status(self, zone: int) -> ZoneEQStatus:
        return await self._connection.send_message(
            _format_zone_eq_request(zone), ZONE_EQ_STATUS
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda treble: treble in TREBLE_RANGE)
    async def set_treble(self, zone: int, treble: int) -> ZoneEQStatus:
        return await self._connection.send_message(
            _format_set_treble(zone, treble), ZONE_EQ_STATUS
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda bass: bass in BASS_RANGE)
    async def set_bass(self, zone: int, bass: int) -> ZoneEQStatus:
        return await self._connection.send_message(
            _format_set_bass(zone, bass), ZONE_EQ_STATUS
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    async def set_loudness_comp(self, zone: int, loudness_comp: bool) -> ZoneEQStatus:
        return await self._connection.send_message(
            _format_set_loudness_comp(zone, loudness_comp), ZONE_EQ_STATUS
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda position: position in BALANCE_POSITIONS)
    @icontract.require(lambda balance: balance in BALANCE_RANGE)
    async def set_balance(self, zone: int, position: str, balance: int) -> ZoneEQStatus:
        return await self._connection.send_message(
            _format_set_balance(zone, position, balance), ZONE_EQ_STATUS
        )

    """
    Zone Button Commands
    """

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    async def zone_button_play_pause(self, zone: int) -> Union[ZoneButton, ZoneStatus]:
        return await self._connection.send_message(
            _format_zone_button_request(zone, ZONE_BUTTON_PLAY_PAUSE),
            (ZONE_BUTTON, ZONE_STATUS),
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    async def zone_button_prev(self, zone: int) -> Union[ZoneButton, ZoneStatus]:
        return await self._connection.send_message(
            _format_zone_button_request(zone, ZONE_BUTTON_PREV),
            (ZONE_BUTTON, ZONE_STATUS),
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    async def zone_button_next(self, zone: int) -> Union[ZoneButton, ZoneStatus]:
        return await self._connection.send_message(
            _format_zone_button_request(zone, ZONE_BUTTON_NEXT),
            (ZONE_BUTTON, ZONE_STATUS),
        )

    """
    Zone Volume Configuration Commands
    """

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    async def zone_volume_configuration(self, zone: int) -> ZoneVolumeConfiguration:
        return await self._connection.send_message(
            _format_zone_vol_configuration(zone), ZONE_VOLUME_CONFIGURATION
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda volume: volume in VOLUME_RANGE)
    async def zone_volume_max(self, zone: int, volume: int) -> ZoneVolumeConfiguration:

        return await self._connection.send_message(
            _format_zone_vol_max(zone, volume), ZONE_VOLUME_CONFIGURATION
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda volume: volume in VOLUME_RANGE)
    async def zone_volume_initial(
        self, zone: int, volume: int
    ) -> ZoneVolumeConfiguration:
        return await self._connection.send_message(
            _format_zone_vol_ini(zone, volume), ZONE_VOLUME_CONFIGURATION
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda volume: volume in VOLUME_RANGE)
    async def zone_volume_page(self, zone: int, volume: int) -> ZoneVolumeConfiguration:
        return await self._connection.send_message(
            _format_zone_vol_page(zone, volume), ZONE_VOLUME_CONFIGURATION
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda volume: volume in VOLUME_RANGE)
    async def zone_volume_party(
        self, zone: int, volume: int
    ) -> ZoneVolumeConfiguration:
        return await self._connection.send_message(
            _format_zone_vol_party(zone, volume), ZONE_VOLUME_CONFIGURATION
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    async def zone_volume_reset(
        self, zone: int, reset: bool
    ) -> ZoneVolumeConfiguration:
        return await self._connection.send_message(
            _format_zone_vol_reset(zone, reset), ZONE_VOLUME_CONFIGURATION
        )

    """
    System Commands
    """

    @locked
    async def set_page(self, page: bool, query_zone_states: bool = True) -> None:
        await self._connection.send_message_without_reply(_format_set_page(page))
        if query_zone_states:
            """
            The paging command does not cause zone status change messages to be
            to emitted by the Nuvo, need to query these directly to ensure
            anything tracking zone state is updated.

            We're in a locked coro so can't call other commands directly or
            they won't be able to acquire the lock, so create a task instead
            and allow us to return from this coro to release the lock.
            """
            loop = asyncio.get_running_loop()
            loop.call_later(1, lambda: loop.create_task(self._get_zone_states()))

    @locked
    async def all_off(self, query_zone_states: bool = True) -> ZoneAllOff:
        all_off = await self._connection.send_message("ALLOFF", ZONE_ALL_OFF)
        if query_zone_states:
            loop = asyncio.get_running_loop()
            loop.call_later(1, lambda: loop.create_task(self._get_zone_states()))
        return all_off

    @locked
    async def get_version(self) -> Version:
        return await self._connection.send_message("VER", SYSTEM_VERSION)


class NuvoSync:
    def __init__(self, port_url: str, model: str, retries: Optional[int] = None):
        _set_model_globals(model)
        _LOGGER.info('Attempting connection - "%s"', port_url)
        self._retry_request = SyncRequest(port_url, model, retries)

    """
    Zone Status Commands
    """

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @synchronized
    def zone_status(self, zone: int) -> Optional[ZoneStatus]:
        rtn: Optional[ZoneStatus]
        rtn = self._retry_request(
            _format_zone_status_request(zone), "Zone Status", ZoneStatus
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @synchronized
    def set_power(self, zone: int, power: bool) -> Optional[ZoneStatus]:
        rtn: Optional[ZoneStatus]
        rtn = self._retry_request(
            _format_set_power(zone, power), "Zone Power", ZoneStatus
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda source: source in SOURCE_RANGE)
    @synchronized
    def set_source(self, zone: int, source: int) -> Optional[ZoneStatus]:
        rtn: Optional[ZoneStatus]
        rtn = self._retry_request(
            _format_set_source(zone, source), "Zone Source", ZoneStatus
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @synchronized
    def set_next_source(self, zone: int) -> Optional[ZoneStatus]:
        rtn: Optional[ZoneStatus]
        rtn = self._retry_request(
            _format_set_next_source(zone), "Zone Next Source", ZoneStatus
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @synchronized
    def set_mute(self, zone: int, mute: bool) -> Optional[ZoneStatus]:
        rtn: Optional[ZoneStatus]
        rtn = self._retry_request(_format_set_mute(zone, mute), "Zone Mute", ZoneStatus)
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda volume: volume in VOLUME_RANGE)
    @synchronized
    def set_volume(self, zone: int, volume: int) -> Optional[ZoneStatus]:
        rtn: Optional[ZoneStatus]
        rtn = self._retry_request(
            _format_set_volume(zone, volume), "Zone Volume", ZoneStatus
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @synchronized
    def set_dnd(self, zone: int, dnd: bool) -> Optional[ZoneStatus]:
        rtn: Optional[ZoneStatus]
        rtn = self._retry_request(_format_set_dnd(zone, dnd), "Zone DND", ZoneStatus)
        return rtn

    @synchronized
    def restore_zone(self, status: ZoneStatus) -> Optional[ZoneStatus]:
        rtn: Optional[ZoneStatus]
        self.set_power(status.zone, status.power)  # ZoneStatus
        self.set_mute(status.zone, status.mute)  # ZoneStatus
        self.set_volume(status.zone, status.volume)  # ZoneStatus
        rtn = self.set_source(status.zone, status.source)  # ZoneStatus
        return rtn

    """
    Zone EQ Status Commands
    """

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @synchronized
    def zone_eq_status(self, zone: int) -> Optional[ZoneEQStatus]:
        rtn: Optional[ZoneEQStatus]
        rtn = self._retry_request(
            _format_zone_eq_request(zone), "Zone EQ Status", ZoneEQStatus
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda treble: treble in TREBLE_RANGE)
    @synchronized
    def set_treble(self, zone: int, treble: int) -> Optional[ZoneEQStatus]:
        rtn: Optional[ZoneEQStatus]
        rtn = self._retry_request(
            _format_set_treble(zone, treble), "Zone Treble", ZoneEQStatus
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda bass: bass in BASS_RANGE)
    @synchronized
    def set_bass(self, zone: int, bass: int) -> Optional[ZoneEQStatus]:
        rtn: Optional[ZoneEQStatus]
        rtn = self._retry_request(
            _format_set_bass(zone, bass), "Zone Bass", ZoneEQStatus
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @synchronized
    def set_loudness_comp(
        self, zone: int, loudness_comp: bool
    ) -> Optional[ZoneEQStatus]:
        rtn: Optional[ZoneEQStatus]
        rtn = self._retry_request(
            _format_set_loudness_comp(zone, loudness_comp),
            "Zone Loudness Comp",
            ZoneEQStatus,
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda position: position in BALANCE_POSITIONS)
    @icontract.require(lambda balance: balance in BALANCE_RANGE)
    @synchronized
    def set_balance(
        self, zone: int, position: str, balance: int
    ) -> Optional[ZoneEQStatus]:
        rtn: Optional[ZoneEQStatus]
        rtn = self._retry_request(
            _format_set_balance(zone, position, balance), "Zone Balance", ZoneEQStatus,
        )
        return rtn

    """
    Zone Configuration Commands
    """

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @synchronized
    def zone_configuration(self, zone: int) -> Optional[ZoneConfiguration]:
        # assert check_argument_types()
        rtn: Optional[ZoneConfiguration]
        rtn = self._retry_request(
            _format_zone_configuration_request(zone),
            "Zone Configuration",
            ZoneConfiguration,
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(
        lambda sources: not len(sources)
        or all([src in SourceMask.__members__.keys() for src in sources])
    )
    @synchronized
    def zone_set_source_mask(
        self, zone: int, sources: List[str]
    ) -> Optional[ZoneConfiguration]:
        """
        sources: [] to disallow all sources or ['SOURCE1', 'SOURCE3'...]
        """
        mask = SourceMask(0)
        for source in sources:
            mask = mask | SourceMask[source]
        rtn: Optional[ZoneConfiguration]
        rtn = self._retry_request(
            _format_zone_set_source_mask(zone, mask.value),
            "Zone Allowed Sources",
            ZoneConfiguration,
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(
        lambda dnd: not len(dnd)
        or all([option in DndMask.__members__.keys() for option in dnd])
    )
    @synchronized
    def zone_set_dnd_mask(
        self, zone: int, dnd: List[str]
    ) -> Optional[ZoneConfiguration]:
        """
       dnd: [] to clear all DND options or a combo of ['NOMUTE', 'NOPAGE', 'NOPARTY']
        """
        mask = DndMask(0)
        for option in dnd:
            mask = mask | DndMask[option]
        rtn: Optional[ZoneConfiguration]
        rtn = self._retry_request(
            _format_zone_set_dnd_mask(zone, mask.value),
            "Zone DND Options",
            ZoneConfiguration,
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda name: len(name) <= ZONE_NAME_MAX_LENGTH)
    @synchronized
    def zone_set_name(self, zone: int, name: str) -> Optional[ZoneConfiguration]:
        rtn: Optional[ZoneConfiguration]
        rtn = self._retry_request(
            _format_zone_set_name(zone, name), "Zone Name", ZoneConfiguration,
        )
        return rtn

    """
    Source Configuration Commands
    """

    @icontract.require(lambda source: source in SOURCE_RANGE)
    @synchronized
    def source_status(self, source: int) -> Optional[SourceConfiguration]:
        rtn: Optional[SourceConfiguration]
        rtn = self._retry_request(
            _format_source_status_request(source), "Source Status", SourceConfiguration
        )
        return rtn

    @icontract.require(lambda source: source in SOURCE_RANGE)
    @icontract.require(lambda name: len(name) <= SOURCE_NAME_LONG_MAX_LENGTH)
    @synchronized
    def set_source_name(self, source: int, name: str) -> Optional[SourceConfiguration]:
        rtn: Optional[SourceConfiguration]
        rtn = self._retry_request(
            _format_set_source_name(source, name), "Source Name", SourceConfiguration
        )
        return rtn

    @icontract.require(lambda source: source in SOURCE_RANGE)
    @synchronized
    def set_source_enable(
        self, source: int, enable: bool
    ) -> Optional[SourceConfiguration]:
        rtn: Optional[SourceConfiguration]
        rtn = self._retry_request(
            _format_set_source_enable(source, enable),
            "Source Enable",
            SourceConfiguration,
        )
        return rtn

    @icontract.require(lambda source: source in SOURCE_RANGE)
    @icontract.require(lambda gain: gain in SOURCE_GAIN_RANGE)
    @synchronized
    def set_source_gain(self, source: int, gain: int) -> Optional[SourceConfiguration]:
        rtn: Optional[SourceConfiguration]
        rtn = self._retry_request(
            _format_set_source_gain(source, gain), "Source Gain", SourceConfiguration
        )
        return rtn

    @icontract.require(lambda source: source in SOURCE_RANGE)
    @synchronized
    def set_source_nuvonet(
        self, source: int, nuvonet: bool
    ) -> Optional[SourceConfiguration]:
        rtn: Optional[SourceConfiguration]
        rtn = self._retry_request(
            _format_set_source_nuvonet(source, nuvonet),
            "Source Nuvonet",
            SourceConfiguration,
        )
        return rtn

    @icontract.require(lambda source: source in SOURCE_RANGE)
    @icontract.require(lambda shortname: len(shortname) <= SOURCE_NAME_SHORT_MAX_LENGTH)
    @synchronized
    def set_source_shortname(
        self, source: int, shortname: str
    ) -> Optional[SourceConfiguration]:
        rtn: Optional[SourceConfiguration]
        rtn = self._retry_request(
            _format_set_source_shortname(source, shortname),
            "Source Short Name",
            SourceConfiguration,
        )
        return rtn

    """
    Zone Volume Configuration Commands
    """

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @synchronized
    def zone_volume_configuration(self, zone: int) -> Optional[ZoneVolumeConfiguration]:
        rtn: Optional[ZoneVolumeConfiguration]
        rtn = self._retry_request(
            _format_zone_vol_configuration(zone),
            "Zone Volume Configuration",
            ZoneVolumeConfiguration,
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda volume: volume in VOLUME_RANGE)
    @synchronized
    def zone_volume_max(
        self, zone: int, volume: int
    ) -> Optional[ZoneVolumeConfiguration]:
        rtn: Optional[ZoneVolumeConfiguration]
        rtn = self._retry_request(
            _format_zone_vol_max(zone, volume),
            "Zone Volume Configuration Max",
            ZoneVolumeConfiguration,
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda volume: volume in VOLUME_RANGE)
    @synchronized
    def zone_volume_initial(
        self, zone: int, volume: int
    ) -> Optional[ZoneVolumeConfiguration]:
        rtn: Optional[ZoneVolumeConfiguration]
        rtn = self._retry_request(
            _format_zone_vol_ini(zone, volume),
            "Zone Volume Configuration Initial",
            ZoneVolumeConfiguration,
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda volume: volume in VOLUME_RANGE)
    @synchronized
    def zone_volume_page(
        self, zone: int, volume: int
    ) -> Optional[ZoneVolumeConfiguration]:
        rtn: Optional[ZoneVolumeConfiguration]
        rtn = self._retry_request(
            _format_zone_vol_page(zone, volume),
            "Zone Volume Configuration Page",
            ZoneVolumeConfiguration,
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda volume: volume in VOLUME_RANGE)
    @synchronized
    def zone_volume_party(
        self, zone: int, volume: int
    ) -> Optional[ZoneVolumeConfiguration]:
        rtn: Optional[ZoneVolumeConfiguration]
        rtn = self._retry_request(
            _format_zone_vol_party(zone, volume),
            "Zone Volume Configuration Party",
            ZoneVolumeConfiguration,
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @synchronized
    def zone_volume_reset(
        self, zone: int, reset: bool
    ) -> Optional[ZoneVolumeConfiguration]:
        rtn: Optional[ZoneVolumeConfiguration]
        rtn = self._retry_request(
            _format_zone_vol_reset(zone, reset),
            "Zone Volume Configuration Reset",
            ZoneVolumeConfiguration,
        )
        return rtn

    """
    System Commands
    """

    # @synchronized
    # def set_page_on(self) -> None:
    #     self._process_request("PAGE1")

    # @synchronized
    # def set_page_off(self) -> None:
    #     self._process_request("PAGE0")

    @synchronized
    def get_version(self) -> Optional[Version]:
        rtn: Optional[Version]
        rtn = self._retry_request("VER", "Request Version", Version)
        return rtn


def _is_int(s: Union[int, float, str]) -> bool:
    try:
        int(s)
        return True
    except ValueError:
        return False


"""
System Command Formas
"""


def _format_set_page(page: bool) -> str:
    return "PAGE{}".format(int(page))


"""
Zone EQ Formats
"""


def _format_zone_eq_request(zone: int) -> str:
    return "ZCFG{}EQ?".format(zone)


def _format_set_treble(zone: int, treble: int) -> str:
    # treble = int(max(12, min(treble, -12)))
    return "ZCFG{}TREB{}".format(int(zone), int(treble))


def _format_set_bass(zone: int, bass: int) -> str:
    return "ZCFG{}BASS{}".format(int(zone), int(bass))


def _format_set_loudness_comp(zone: int, loudness_comp: bool) -> str:
    return "ZCFG{}LOUDCMP{}".format(int(zone), int(loudness_comp))


def _format_set_balance(zone: int, position: str, balance: int) -> str:
    return "ZCFG{}BAL{}{}".format(int(zone), position, balance)


"""
Zone Status Formats
"""


def _format_zone_status_request(zone: int) -> str:
    return "Z{}STATUS?".format(zone)


def _format_set_power(zone: int, power: bool) -> str:
    zone = int(zone)
    if power:
        return "Z{}ON".format(zone)
    else:
        return "Z{}OFF".format(zone)


def _format_set_source(zone: int, source: int) -> str:
    source = int(max(1, min(int(source), 6)))
    return "Z{}SRC{}".format(int(zone), source)


def _format_set_next_source(zone: int) -> str:
    return "Z{}SRC+".format(int(zone))


def _format_set_volume(zone: int, volume: int) -> str:
    return "Z{}VOL{}".format(zone, volume)


def _format_set_mute(zone: int, mute: bool) -> str:
    if mute:
        return "Z{}MUTEON".format(int(zone))
    else:
        return "Z{}MUTEOFF".format(int(zone))


def _format_set_dnd(zone: int, dnd: bool) -> str:
    if dnd:
        command = "ON"
    else:
        command = "OFF"

    return "Z{}DND{}".format(int(zone), command)


"""
Zone Configuration Formats
"""


def _format_zone_configuration_request(zone: int) -> str:
    return "ZCFG{}STATUS?".format(int(zone))


def _format_zone_set_source_mask(zone: int, sources: int) -> str:
    return "ZCFG{}SOURCES{}".format(zone, sources)


def _format_zone_set_dnd_mask(zone: int, mask: int) -> str:
    return "ZCFG{}DND{}".format(zone, mask)


def _format_zone_set_name(zone: int, name: str) -> str:
    return 'ZCFG{}NAME"{}"'.format(zone, name)


"""
Source Commands Formats
"""


def _format_source_status_request(source: int) -> str:
    return "SCFG{}STATUS?".format(int(source))


def _format_set_source_enable(source: int, enable: bool) -> str:
    return "SCFG{}ENABLE{}".format(source, int(enable))


def _format_set_source_name(source: int, name: str) -> str:
    return 'SCFG{}NAME"{}"'.format(source, name)


def _format_set_source_gain(source: int, gain: int) -> str:
    return "SCFG{}GAIN{}".format(source, gain)


def _format_set_source_nuvonet(source: int, nuvonet: bool) -> str:
    return "SCFG{}NUVONET{}".format(source, int(nuvonet))


def _format_set_source_shortname(source: int, shortname: str) -> str:
    return 'SCFG{}SHORTNAME"{}"'.format(source, shortname)


"""
Zone Volume Configuration Formats
"""


def _format_zone_vol_configuration(zone: int) -> str:
    return "ZCFG{}VOL?".format(zone)


def _format_zone_vol_max(zone: int, volume: int) -> str:
    return "ZCFG{}MAXVOL{}".format(zone, volume)


def _format_zone_vol_ini(zone: int, volume: int) -> str:
    return "ZCFG{}INIVOL{}".format(zone, volume)


def _format_zone_vol_page(zone: int, volume: int) -> str:
    return "ZCFG{}PAGEVOL{}".format(zone, volume)


def _format_zone_vol_party(zone: int, volume: int) -> str:
    return "ZCFG{}PARTYVOL{}".format(zone, volume)


def _format_zone_vol_reset(zone: int, reset: bool) -> str:
    return "ZCFG{}VOLRST{}".format(zone, int(reset))


"""
Zone Button Formats
"""


def _format_zone_button_request(zone: int, button: str) -> str:
    return "Z{}{}".format(zone, button)
