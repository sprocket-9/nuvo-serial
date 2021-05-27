from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from copy import deepcopy
from dataclasses import asdict, replace
import logging
from typing import Any, Callable, Iterable, Optional, Union, List, Set

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
    EMIT_LEVEL_ALL,
    EMIT_LEVEL_EXTERNAL,
    EMIT_LEVEL_INTERNAL,
    EMIT_LEVEL_NONE,
    PARTY_MODE_ENABLED,
    PARTY_MODE_DISABLED,
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
    SYSTEM_PAGING,
    SYSTEM_PARTY,
    SYSTEM_VERSION,
    OK_RESPONSE,
)
from nuvo_serial.exceptions import ModelMismatchError
from nuvo_serial.message import (
    DndMask,
    OKResponse,
    Paging,
    Party,
    SourceConfiguration,
    SourceMask,
    ZoneAllOff,
    ZoneButton,
    ZoneConfiguration,
    ZoneEQStatus,
    ZoneStatus,
    ZoneVolumeConfiguration,
    Version,
    MSG_CLASS_KEYS,
    MSG_CLASS_QUERY_ZONE_STATUS,
    MSG_CLASS_TRACK,
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

    global SLAVE_TO_RANGE
    SLAVE_TO_RANGE = range(
        config[model]["zones"]["slave_to"]["min"],
        config[model]["zones"]["slave_to"]["max"] + 1,
        config[model]["zones"]["slave_to"]["step"],
    )

    global GROUP_RANGE
    GROUP_RANGE = range(
        config[model]["zones"]["group"]["min"],
        config[model]["zones"]["group"]["max"] + 1,
        config[model]["zones"]["group"]["step"],
    )


class StateTrack:
    def __init__(self, nuvo: NuvoAsync, model: str) -> None:
        self._state: dict = {}
        self._previous_state: dict = {}
        self._clear_party_tracker()
        self._nuvo = nuvo
        self._model = model
        self._initial_state_retrieval_completed = False

    def setup_subscribers(self) -> None:
        """Add callbacks for Nuvo message types."""

        for msg_type in MSG_CLASS_TRACK[self._model]:
            self._nuvo._bus.add_subscriber(self._state_tracker, msg_type, internal=True)

        # for msg_type in MSG_CLASS_QUERY_ZONE_STATUS[self._model]:
        #     self._nuvo._bus.add_subscriber(
        #         self._event_zone_query, msg_type, internal=True
        #     )

    def setup_special_subscribers(self) -> None:
        for msg_type in MSG_CLASS_QUERY_ZONE_STATUS[self._model]:
            # if msg_type == SYSTEM_PARTY:
            #     self._nuvo._bus.add_subscriber(
            #         self._party_mode_handler, msg_type, internal=True
            #     )
            # else:

            self._nuvo._bus.add_subscriber(
                self._event_zone_query, msg_type, internal=True
            )

    async def get_initial_states(self) -> None:
        """Query Nuvo for its current state."""

        self._initial_state_retrieval_completed = False

        await self._get_party_status()
        await self._get_zone_states()
        await self._get_zone_configurations()
        await self._get_zone_volume_configurations()
        await self._get_zone_eq_configurations()
        await self._get_source_configurations()
        await self._nuvo.get_version()
        self._initial_state_retrieval_completed = True

    async def _get_zone_states(
        self,
        exclusions: Optional[Iterable[int]] = None,
        inclusions: Optional[Iterable[int]] = None,
    ) -> List[Any]:
        """Get ZoneStatus for all zones."""

        exclusions = [] if exclusions is None else exclusions
        inclusions = [] if inclusions is None else inclusions
        # if inclusions is not None and not inclusions:
        #     return []
        # zone_list = inclusions if inclusions else ZONE_RANGE_PHYSICAL
        if inclusions:
            _LOGGER.debug("Zone list inclusions = %s", inclusions)
        zone_states = []
        for zone in ZONE_RANGE_PHYSICAL:
            # for zone in zone_list:
            if zone in exclusions:
                continue
            if inclusions and zone not in inclusions:
                continue
            zone_states.append(await self._nuvo.zone_status(zone))
        return zone_states

    async def _get_zone_configurations(self) -> None:
        """Get ZoneConfiguration for all zones."""

        for zone in ZONE_RANGE_PHYSICAL:
            await self._nuvo.zone_configuration(zone)

    async def _get_zone_eq_configurations(self) -> None:
        """Get ZoneEQ for all zones."""

        for zone in ZONE_RANGE_PHYSICAL:
            await self._nuvo.zone_eq_status(zone)

    async def _get_zone_volume_configurations(self) -> None:
        """Get ZoneVolume for all zones."""

        for zone in ZONE_RANGE_PHYSICAL:
            await self._nuvo.zone_volume_configuration(zone)

    async def _get_source_configurations(self) -> None:
        """Get SourceConfiguration for all zones."""

        for source in SOURCE_RANGE:
            await self._nuvo.source_configuration(source)

    @locked
    async def _get_party_status(self) -> Party:
        """Get Party status..."""

        return await self._nuvo._connection.send_message(
            _format_set_party_host(0, False), SYSTEM_PARTY
        )

    @property
    def party_active(self) -> bool:
        """Return the Party status."""

        return self._state[SYSTEM_PARTY][MSG_CLASS_KEYS[SYSTEM_PARTY]].party_host

    @property
    def party_host(self) -> int:
        """Return the Party host zone id."""

        return self._state[SYSTEM_PARTY][MSG_CLASS_KEYS[SYSTEM_PARTY]].zone

    async def _state_tracker(self, message: dict[str, Any]) -> None:
        """Track Nuvo state.

        Event callback to receive all the dataclasses created from received nuvo
        messages.
        Stores each one in memory, merging any changes received.
        {
            'ZoneStatus': {
                1: dataclass',
                2: dataclass,
                ...
            }
            'ZoneConfiguration': {
                1: dataclass',
                2: dataclass,
                ...
            }
        }
        """

        self._previous_state = deepcopy(self._state)
        msg_type = message["event_name"]
        new_d_class = message["event"]
        event_entity = MSG_CLASS_KEYS[msg_type]
        new_d_class_asdict = asdict(message["event"])
        event_data = self._state.setdefault(msg_type, {})

        if event_entity in ("zone", "source"):
            existing_d_class = event_data.get(new_d_class_asdict[event_entity], None)
            key = new_d_class_asdict[event_entity]
        else:
            existing_d_class = event_data.get(event_entity, None)
            key = event_entity

        if existing_d_class:
            # merge data rather than replace, so original object remains
            for k, v in new_d_class_asdict.items():
                setattr(existing_d_class, k, v)
        else:
            event_data[key] = new_d_class

        if self._initial_state_retrieval_completed:
            await self._zone_group_state_tracker(message)

            if msg_type == SYSTEM_PARTY:
                await self._party_mode_handler(message)

    async def _zone_group_state_tracker(self, message: dict[str, Any]) -> None:
        """Handle ZoneStatus updates for:
            Party mode
            Master/Slave mode
            Zone groups
        """

        msg_type = message["event_name"]
        msg = message["event"]
        # event_entity = MSG_CLASS_KEYS[msg_type]

        """
        PARTY MODE

        One zone (host) controls all other zones (guests).

        All zones that do not have Party mode disabled (ZoneConfiguration.dnd) are
        turned on and set to ZoneVolume.party_vol setting.

        Party host changes volume, mute, source for all guest zones, Nuvo only emits
        ZoneStatus for host zone.

        Guest zone settings cannot be overriden by party mode host - e.g. max_vol,
        permitted sources.  A setting from host violating any guest setting will
        be accepted by the Nuvo, set on permitted guests, but cause the violated
        guest zone to fall out of state mirror with host until a non-violating setting
        by host brings it back in step.

        ZoneStatus for guest zones CAN be queried.

        ZoneStatus.vol/mute for a guest zone can be changed but subsequent host
        changes will override this.

        ZoneStatus.src for a guest zone cannot be changed, Nuvo silently swallows
        request.

        Powering off host zone does not switch the guest zones off.

        Switching former host zone back on does NOT put it back in party host mode.

        --

        Ensure when host ZoneStatus changes, guest zones are queried and
        emitted to listeners. Query Nuvo for individual guest zones rather than
        mirror then emit host zone state, as settings like permitted sources
        and max_vol do not get overriden by being in a party, so configuration
        set by host that violates a guest setting will not be set on that
        guest and state cannot be guaranteed to match.

        To prevent receiving the party host ZoneStatus again and causing a loop:
            Exclude the party host zone itself
            Exclude any zone slaved to the party host as this returns the master zone
            ZoneStatus, not the slaved zone.
            Exclude zones with Party mode disabled
            Exclude slaved zones
        """

        if (
            msg_type == ZONE_STATUS
            and self.party_active
            and self.party_host == msg.zone
        ):
            await self._party_host_zone_status_handler(msg)

        """
        MASTER/SLAVE ZONES

        One master, many slaved zones.

        Master zone then controls all aspects of slaved zone: power, volume, source etc

        Relationships can be chained - a slaved zone can be a master zone for
        other zones.

        From Nuvo API docs:
        'When a zone is slaved to another zone, the Main Processor Unit only
        outputs zone status commands for the master zone. The slaved zone must
        treat the zone status commands that are addressed to the master zone as
        if they were addressed directly to the slaved zone.'

        ZoneStatus request for slave zone, returns master
        ZoneStatus(zone=master_zone_id...)

        Nuvo ZoneStatus message contains a slave_eq=0/1 field which is not in serial
        control API document so do not know the API command to modify this.  There is
        a "Slave EQ Settings" checkbox for this field in the Windows Nuvo Configurator
        application.

        Slaving a zone does not set slave_eq to 1 automatically, its set to 0.

        ZoneEQ for a slaved zone with slave_eq=1 can be queried, it doesn't return
        the master zone id.

        ZoneEQ for a slaved zone with slave_eq=1 can be changed, it also changes the
        master zone and other slaved zones ZoneEQ.

        When in a master/slave relationship setting the Master or ZoneEQ using their
        respective IDs will sync each others EQ, but the ZoneEQ message returned
        contains their own ID.  This means HASS will not reflect a slaves EQ properties
        if the Masters EQ is changed, and vice versa.  NOt sure how to handle this.

        Update and emit Slave zones ZoneStatus if Master zone's ZoneStatus changes.

        Requesting a slaved zone's ZoneStatus returns the master's ZoneStatus so can't
        use this to keep state in step.


        """
        # ZoneStatus rcvd from a master
        # Update and emit slave zones ZoneStatus
        # Will also handle updating slave zones for a master zone which is currently a
        # party guest
        if msg_type == ZONE_STATUS and self._slave_zones_for_zone(zone=msg.zone):
            self._master_zone_status_handler(msg)

        # Group membership handler
        # Filter:
        # Zone is ON
        # Zone in a group
        # Zone is not in a party
        # Zone source has changed

        if (msg_type == ZONE_STATUS and msg.zone == 7):
            _LOGGER.debug("Zone %d FOUND7: %s", msg.zone, msg)
        if (
            msg_type == ZONE_STATUS
            and msg.power
            and self._get_group_membership(zone=msg.zone)
            and msg.zone not in self._get_zones_in_party()
            and not self._zone_switching_on(msg.zone)
            and msg.source != self._get_previous_source(msg.zone)
        ):
            self._group_member_zone_status_handler(msg)

        if msg_type == ZONE_EQ_STATUS:
            # ZoneEQ rcvd from a master
            if self._slave_zones_for_zone(zone=msg.zone):
                self._master_zone_eq_handler(msg)
            # ZoneEQ rcvd from a slave with slave_eq=True
            elif self._get_master_zone_for_slave(
                slave_zone=msg.zone
            ) and self._slave_eq_enabled(msg.zone):
                self._slave_zone_eq_handler(msg)

    async def _party_host_zone_status_handler(self, msg: ZoneStatus) -> None:
        """On receiving party host ZoneStatus, request party guests ZoneStatus.
        """
        inclusions = self._state[PARTY_MODE_ENABLED].difference({msg.zone})
        if inclusions:
            _LOGGER.debug(f"GROUP: PARTY GUEST ZONE UPDATES FOR: {inclusions}")
            asyncio.create_task(self._get_zone_states(inclusions=inclusions))

    def _master_zone_status_handler(self, msg: ZoneStatus) -> None:
        """ZoneStatus rcvd from a master.
        Update and emit slave zone ZoneStatus."""

        new_z_states = []

        for slave_zone_id in self._slave_zones_for_zone(zone=msg.zone):
            new_slave_z_status = replace(msg, zone=slave_zone_id)
            self._state[ZONE_STATUS][slave_zone_id] = new_slave_z_status
            new_z_states.append(new_slave_z_status)

        self._nuvo._bus.set_emit_level(EMIT_LEVEL_EXTERNAL)
        for z_status in new_z_states:
            _LOGGER.debug(f"GROUP: SLAVE ZONE UPDATE: {z_status}")
            self._nuvo._bus.emit_event(
                event_name=ZONE_STATUS, event=z_status)
        self._nuvo._bus.set_emit_level(EMIT_LEVEL_ALL)

    def _master_zone_eq_handler(self, msg: ZoneEQStatus) -> None:
        """ZoneEQ rcvd from a master.
        Update and emit slave zone ZoneEQ."""

        # Master zone ZoneEQ msg rcvd
        # Update slave zones with slave_eq=1
        if self._slave_zones_for_zone(zone=msg.zone):
            new_z_eqs = []

            for slave_zone_id in self._slave_zones_for_zone(zone=msg.zone):
                if self._slave_eq_enabled(slave_zone_id):
                    new_slave_z_eq = replace(msg, zone=slave_zone_id)
                    self._state[ZONE_EQ_STATUS][slave_zone_id] = new_slave_z_eq
                    new_z_eqs.append(new_slave_z_eq)

            self._nuvo._bus.set_emit_level(EMIT_LEVEL_EXTERNAL)
            for z_eq in new_z_eqs:
                _LOGGER.debug(f"GROUP: MASTER_EQ UPDATING SLAVE ZONES: {z_eq}")
                self._nuvo._bus.emit_event(
                    event_name=ZONE_EQ_STATUS, event=z_eq)
            self._nuvo._bus.set_emit_level(EMIT_LEVEL_ALL)

    def _slave_zone_eq_handler(self, msg: ZoneEQStatus) -> None:
        """ZoneEQ rcvd from a slave with slave_eq=True.
        Update and emit master and fellow slave zone ZoneEQ."""

        # Slave zone ZoneEQ msg rcvd
        # Update fellow slave zones with slave_eq=1
        # Update the master ZoneEQ
        master_zone = self._get_master_zone_for_slave(slave_zone=msg.zone)
        slave_zones = self._slave_zones_for_zone(zone=master_zone)
        zones_for_update = [master_zone]
        for slave_zone in slave_zones:
            if self._slave_eq_enabled(slave_zone):
                zones_for_update.append(slave_zone)

        new_z_eqs = []

        for zone_id in zones_for_update:
            new_z_eq = replace(msg, zone=zone_id)
            self._state[ZONE_EQ_STATUS][zone_id] = new_z_eq
            new_z_eqs.append(new_z_eq)

        self._nuvo._bus.set_emit_level(EMIT_LEVEL_EXTERNAL)
        for z_eq in new_z_eqs:
            _LOGGER.debug(f"GROUP: SLAVE_EQ UPDATING MASTER AND OTHER SLAVES: {z_eq}")
            self._nuvo._bus.emit_event(
                event_name=ZONE_EQ_STATUS, event=z_eq)
        self._nuvo._bus.set_emit_level(EMIT_LEVEL_ALL)

    def _group_member_zone_status_handler(self, msg: ZoneStatus) -> None:
        """ZoneStatus rcvd from a Group member.
        For all zones in the group and not currently in a party, update Source
        and emit to listeners.
        """
        # Only the Source is shared amongst groups so check if this has changed
        # as this handler will also run for volume changes etc

        _LOGGER.debug("GROUP: GROUP MEMBER HANDLER FOR ZONE: %s", msg.zone)
        # current_source = self._get_current_source(msg.zone)
        # if current_source == msg.source:
        #     _LOGGER.debug("GROUP: GROUP MEMBER HANDLER FOR ZONE: %s SOURCE MATCH, NOOP", msg.zone)
        #     return

        party_members = self._get_zones_in_party()

        # Being in a party overrides being in a group
        # if self.party_active:
        #     if msg.zone in party_members:
        #         return

        group_members = self._get_group_members(
            group=self._get_group_membership(zone=msg.zone)
        )
        fellow_group_members = group_members.difference({msg.zone})
        party_members = self._get_zones_in_party()
        fellow_group_members_not_partying = fellow_group_members.difference(party_members)
        _LOGGER.debug("GROUP: GROUP MEMBERS %s", group_members)
        _LOGGER.debug("GROUP: GROUP MEMBERS NOT IN PARTY %s", fellow_group_members_not_partying)
        _LOGGER.debug("GROUP: PARTY MEMBERS: %s", party_members)

        if not fellow_group_members_not_partying:
            _LOGGER.debug("GROUP: GROUP MEMBER SOURCE CHANGE NO UPDATES TO MAKE")
            return
        # else:
        #     _LOGGER.debug(
        #         "GROUP: GROUP MEMBER SOURCE CHANGE UPDATES FOR %s",
        #         fellow_group_members_not_partying,
        #     )

        new_z_states = []

        for zone_id in fellow_group_members_not_partying:
            current_zone_status = self._get_zone_status_from_state(zone_id)
            if current_zone_status.source != msg.source and self._permitted_source_for_zone(zone_id, msg.source):
                _LOGGER.debug(
                    "GROUP: GROUP MEMBER SOURCE CHANGE UPDATES FOR ZONE ID %d",
                    zone_id,
                )
                new_z_status = replace(current_zone_status, source=msg.source)
                self._state[ZONE_STATUS][zone_id] = new_z_status
                new_z_states.append(new_z_status)
        self._nuvo._bus.set_emit_level(EMIT_LEVEL_EXTERNAL)
        if not new_z_states:
            _LOGGER.debug("GROUP: GROUP MEMBER SOURCE CHANGE NO ZONE STATUS UPDATES TO MAKE")
        for z_status in new_z_states:
            _LOGGER.debug(
                "GROUP: GROUP MEMBER SOURCE CHANGE UPDATE FOR ZONE %d - ZONE INITIATOR: %d NEW SOURCE: %d",  # noqa
                z_status.zone,
                msg.zone,
                msg.source
            )
            self._nuvo._bus.emit_event(event_name=ZONE_STATUS, event=z_status)
        self._nuvo._bus.set_emit_level(EMIT_LEVEL_ALL)

    def _get_master_zone_for_slave(self, slave_zone: int) -> int:
        """Return zone id of master zone or 0 if zone is not a slave."""
        z_cfg = self._state[ZONE_CONFIGURATION][slave_zone]
        if z_cfg.enabled:
            return z_cfg.slave_to
        _LOGGER.error(
            "STATE_TRACKER:ANOMALY:ATTEMPTED SLAVE_TO MASTER ZONE QUERY FOR DISABLED ZONE ID %d",  # noqa
            slave_zone,
        )
        return 0

    def _slave_zones_for_zone(self, zone: int) -> List[int]:
        """Return a list of zone id's slaved to master zone."""
        slaves = []
        for zone_id, z_cfg in self._state[ZONE_CONFIGURATION].items():  # noqa
            if z_cfg.enabled and z_cfg.slave_to == zone:
                slaves.append(z_cfg.zone)

        return slaves

    def _slave_eq_enabled(self, zone: int) -> bool:
        """Return slave_eq status of zone."""
        z_cfg = self._state[ZONE_CONFIGURATION][zone]
        if z_cfg.enabled:
            return z_cfg.slave_eq

        _LOGGER.error(
            "STATE_TRACKER:ANOMALY:ATTEMPTED SLAVE_EQ ZONE QUERY FOR DISABLED ZONE ID %d",  # noqa
            zone,
        )
        return False

    def _zones_party_mode_disabled(self) -> List[int]:
        """Return a list of zone id's with DND NOPARTY set."""
        no_party_zones = []
        for zone_id, z_cfg in self._state[ZONE_CONFIGURATION].items():
            if z_cfg.enabled and "NOPARTY" in z_cfg.dnd:
                no_party_zones.append(zone_id)

        return no_party_zones

    def _slaved_zones(self) -> Set[int]:
        """Return a list of zone id's with slave_to set."""
        # slaved_zones = []
        slaved_zones: Set[int] = set()
        for zone_id, z_cfg in self._state[ZONE_CONFIGURATION].items():
            if z_cfg.enabled and z_cfg.slave_to:
                slaved_zones.add(zone_id)
                # slaved_zones.append(zone_id)

        return slaved_zones

    def _disabled_zones(self) -> Set[int]:
        """Return a list of zone id's with enabled=False."""
        disabled_zones: Set[int] = set()
        for zone_id, z_cfg in self._state[ZONE_CONFIGURATION].items():
            if not z_cfg.enabled:
                disabled_zones.add(zone_id)

        return disabled_zones

    def _get_group_membership(self, zone: int) -> int:
        """Return id of the group the zone is a member of - 0 means no group."""
        z_cfg = self._state[ZONE_CONFIGURATION][zone]
        if z_cfg.enabled:
            return z_cfg.group
        _LOGGER.error(
            "STATE_TRACKER:ANOMALY:ATTEMPTED GROUP QUERY FOR DISABLED ZONE ID: %d",
            zone,
        )
        return 0

    def _get_group_members(self, group: int) -> Set[int]:
        """Return set of zone ids in group."""

        grouped_zones: Set[int] = set()
        for zone_id, z_cfg in self._state[ZONE_CONFIGURATION].items():
            if z_cfg.enabled and z_cfg.group == group:
                grouped_zones.add(zone_id)

        return grouped_zones

    def _get_zones_in_party(self) -> Set[int]:
        """Return set of zone ids with part mode enabled."""
        return self._state[PARTY_MODE_ENABLED]

    def _get_current_source(self, zone: int) -> int:
        """Return source id for zone."""
        z_state = self._state[ZONE_STATUS][zone]
        if z_state.power:
            return z_state.source
        _LOGGER.error(
            "STATE_TRACKER:ANOMALY:ATTEMPTED SOURCE QUERY FOR DISABLED ZONE ID: %d",
            zone,
        )
        return 0

    def _get_previous_source(self, zone: int) -> int:
        """Return previous source id for zone."""
        z_state = self._get_zone_status_from_previous_state(zone)
        if z_state.power:
            return z_state.source
        _LOGGER.error(
            "STATE_TRACKER:ANOMALY:ATTEMPTED PREVIOUS SOURCE QUERY FOR DISABLED ZONE ID: %d",
            zone,
        )
        return 0

    def _zone_switching_on(self, zone: int) -> bool:
        """Return True if the zone transitioned from off to on."""
        current_z_status = self._get_zone_status_from_state(zone)
        previous_z_status = self._get_zone_status_from_previous_state(zone)
        if previous_z_status.power is False and current_z_status.power is True:
            return True
        else:
            return False


    def _get_zone_status_from_state(self, zone: int) -> ZoneStatus:
        """Return current ZoneStatus for zone."""
        return self._state[ZONE_STATUS][zone]

    def _get_zone_status_from_previous_state(self, zone: int) -> ZoneStatus:
        """Return previous ZoneStatus for zone."""
        return self._previous_state[ZONE_STATUS][zone]

    def _permitted_source_for_zone(self, zone: int, source: int) -> bool:
        z_cfg = self._state[ZONE_CONFIGURATION][zone]
        permitted_source = False
        for s_id in [int(src.split("SOURCE")[1]) for src in z_cfg.sources]:
            if s_id == source:
                permitted_source = True
                break

        return permitted_source

    async def _event_zone_query(self, message: dict[str, Any]) -> None:
        """Callback to handle received events which require sending a ZoneStatus query.

        Commands *ALLOFF & *PAGE change the zone state but the Nuvo doesn't
        emit ZoneStatus messages to reflect this.  Need to request ZoneStatus
        manually to keep state trackers in step."""

        await self._get_zone_states()

    async def _party_mode_handler(self, message: dict[str, Any]) -> None:
        """Callback to handle party mode being set/unset and track zones which have
        NOPARTY set.

        Due to a Nuvo firmware bug in ZoneConfiguration.dnd bitmask reporting, this
        cannot be used to determine if a zone has NOPARTY set.
        Instead when party mode is enabled, query the zones to check if their volume
        level is set to ZoneVolumeConfiguration.party_vol.
        """

        msg = message["event"]
        # Party mode now disabled
        if not msg.party_host:
            self._clear_party_tracker()
            return

        # Party mode now enabled

        slaved_zones = self._slaved_zones()
        disabled_zones = self._disabled_zones()
        exclusions = slaved_zones.union(disabled_zones)
        self._nuvo._bus.set_emit_level(EMIT_LEVEL_NONE)
        zone_states = await self._get_zone_states(exclusions=exclusions)
        party_participants = []
        non_party_participants = []
        for z_status in zone_states:
            if (
                z_status.power
                and z_status.volume
                == self._state[ZONE_VOLUME_CONFIGURATION][z_status.zone].party_vol
            ):
                party_participants.append(z_status)
            else:
                non_party_participants.append(z_status)

        self._nuvo._bus.set_emit_level(EMIT_LEVEL_ALL)

        self._clear_party_tracker()

        for z in party_participants:
            _LOGGER.debug(f"PARTY_PARTICIPANTS {z}")
            self._state[PARTY_MODE_ENABLED].add(z.zone)
        for z in non_party_participants:
            _LOGGER.debug(f"NON_PARTY_PARTICIPANTS {z}")
            self._state[PARTY_MODE_DISABLED].add(z.zone)

        """
        Now the guest list is known, request ZoneStatus for the party host which will
        kick off updating the party guests and their slaves
        """
        asyncio.create_task(self._get_zone_states(inclusions=[msg.zone]))

    def _clear_party_tracker(self):
        """Clear party tracking state."""
        self._state[PARTY_MODE_ENABLED] = set()
        self._state[PARTY_MODE_DISABLED] = set()


class NuvoAsync:
    def __init__(
        self,
        port_url: str,
        model: str,
        timeout: Optional[float] = None,
        disconnect_time: Optional[float] = None,
        do_model_check: Optional[bool] = True,
        track_state: Optional[bool] = True,
    ):
        self._retry_request = None
        self._port_url = port_url
        self._model = model
        self._timeout = timeout
        self._disconnect_time = disconnect_time
        self._do_model_check = do_model_check
        self._track_state = track_state
        _set_model_globals(self._model)
        self._bus = MsgBus()
        self._physical_zones: int = config[self._model]["zones"]["physical"]

    async def connect(self) -> None:
        if self._track_state:
            self._state_tracker = StateTrack(self, self._model)
            self._state_tracker.setup_subscribers()
        await self._connect()
        if self._track_state:
            await self._state_tracker.get_initial_states()
            self._state_tracker.setup_special_subscribers()

    async def _connect(self) -> None:
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
        """This sets a temporary source lock on a chosen source within the
        zone, it is not related to the ZoneConfiguration DND setting. """
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

    @locked
    @icontract.require(lambda slave_zone: slave_zone in ZONE_RANGE)
    @icontract.require(lambda master_zone: master_zone in SLAVE_TO_RANGE)
    async def zone_slave_to(
        self, slave_zone: int, master_zone: int
    ) -> ZoneConfiguration:
        return await self._connection.send_message(
            _format_zone_slave_to(slave_zone, master_zone), ZONE_CONFIGURATION,
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda group: group in GROUP_RANGE)
    async def zone_join_group(self, zone: int, group: int) -> ZoneConfiguration:
        return await self._connection.send_message(
            _format_zone_join_group(zone, group), ZONE_CONFIGURATION,
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    async def zone_enable(self, zone: int, enable: bool) -> ZoneConfiguration:
        return await self._connection.send_message(
            _format_zone_enable(zone, enable), ZONE_CONFIGURATION,
        )

    """
    Source Configuration Commands
    """

    @locked
    @icontract.require(lambda source: source in SOURCE_RANGE)
    async def source_configuration(self, source: int) -> SourceConfiguration:
        return await self._connection.send_message(
            _format_source_configuration_request(source), SOURCE_CONFIGURATION
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

    These commands simulate pressing the play/plause, prev and next button on a
    zone keypad.

    A command returns a range of responses depending on Nuvo state:
    When:
        zone off -> ZONE_STATUS
        zone on and current selected source is:
            non-nuvonet -> ZONE_BUTTON
            nuvonet     -> OK_RESPONSE

    Assuming when a real zone keypad button is pressed while a Nuvonet source is
    selected, nothing will be emitted by the Nuvo's serial port, and the OK_RESPONSE
    is only for the simulated command.

    """

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    async def zone_button_play_pause(
        self, zone: int
    ) -> Union[ZoneButton, ZoneStatus, OKResponse]:
        return await self._connection.send_message(
            _format_zone_button_request(zone, ZONE_BUTTON_PLAY_PAUSE),
            (ZONE_BUTTON, ZONE_STATUS, OK_RESPONSE),
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    async def zone_button_prev(
        self, zone: int
    ) -> Union[ZoneButton, ZoneStatus, OKResponse]:
        return await self._connection.send_message(
            _format_zone_button_request(zone, ZONE_BUTTON_PREV),
            (ZONE_BUTTON, ZONE_STATUS, OK_RESPONSE),
        )

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    async def zone_button_next(
        self, zone: int
    ) -> Union[ZoneButton, ZoneStatus, OKResponse]:
        return await self._connection.send_message(
            _format_zone_button_request(zone, ZONE_BUTTON_NEXT),
            (ZONE_BUTTON, ZONE_STATUS, OK_RESPONSE),
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
    async def set_page(self, page: bool, query_zone_states: bool = True) -> Paging:
        return await self._connection.send_message(
            _format_set_page(page), SYSTEM_PAGING
        )

    @locked
    async def all_off(self) -> ZoneAllOff:
        return await self._connection.send_message("ALLOFF", ZONE_ALL_OFF)

    @locked
    async def get_version(self) -> Version:
        return await self._connection.send_message("VER", SYSTEM_VERSION)

    @locked
    @icontract.require(lambda zone: zone in ZONE_RANGE)
    async def set_party_host(self, zone: int, enable: bool) -> Party:
        return await self._connection.send_message(
            _format_set_party_host(zone, enable), SYSTEM_PARTY
        )


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
        """This sets a temporary source lock on a chosen source within the
        zone, it is not related to the ZoneConfiguration DND setting. """
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

    @icontract.require(lambda slave_zone: slave_zone in ZONE_RANGE)
    @icontract.require(lambda master_zone: master_zone in SLAVE_TO_RANGE)
    @synchronized
    def zone_slave_to(
        self, slave_zone: int, master_zone: int
    ) -> Optional[ZoneConfiguration]:
        rtn: Optional[ZoneConfiguration]
        rtn = self._retry_request(
            _format_zone_slave_to(slave_zone, master_zone),
            "Zone Slave To",
            ZoneConfiguration,
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @synchronized
    def zone_slave_eq(self, zone: int, slave_eq: bool) -> Optional[ZoneConfiguration]:
        rtn: Optional[ZoneConfiguration]
        rtn = self._retry_request(
            _format_zone_slave_eq(zone, slave_eq), "Zone Slave To", ZoneConfiguration,
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @icontract.require(lambda group: group in GROUP_RANGE)
    @synchronized
    def zone_join_group(self, zone: int, group: int) -> Optional[ZoneConfiguration]:
        rtn: Optional[ZoneConfiguration]
        rtn = self._retry_request(
            _format_zone_join_group(zone, group), "Zone Slave To", ZoneConfiguration,
        )
        return rtn

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @synchronized
    def zone_enable(self, zone: int, enable: bool) -> Optional[ZoneConfiguration]:
        rtn: Optional[ZoneConfiguration]
        rtn = self._retry_request(
            _format_zone_enable(zone, enable), "Zone Slave To", ZoneConfiguration,
        )
        return rtn

    """
    Source Configuration Commands
    """

    @icontract.require(lambda source: source in SOURCE_RANGE)
    @synchronized
    def source_configuration(self, source: int) -> Optional[SourceConfiguration]:
        rtn: Optional[SourceConfiguration]
        rtn = self._retry_request(
            _format_source_configuration_request(source),
            "Source Configuration",
            SourceConfiguration,
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

    @icontract.require(lambda zone: zone in ZONE_RANGE)
    @synchronized
    def set_party_host(self, zone: int, enable: bool) -> Optional[Party]:
        rtn: Optional[Party]
        rtn = self._retry_request(
            _format_set_party_host(zone, enable), "Party Host", Party
        )
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


def _format_set_party_host(zone: int, enable: bool) -> str:
    return "Z{}PARTY{}".format(zone, int(enable))


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


def _format_zone_slave_to(slave_zone: int, master_zone: int) -> str:
    return "ZCFG{}SLAVETO{}".format(slave_zone, master_zone)


def _format_zone_slave_eq(zone: int, slave_eq: bool) -> str:
    return "ZCFG{}SLAVEEQ{}".format(zone, int(slave_eq))


def _format_zone_join_group(zone: int, group: int) -> str:
    return "ZCFG{}GROUP{}".format(zone, group)


def _format_zone_enable(zone: int, enable: bool) -> str:
    return "ZCFG{}ENABLE{}".format(zone, int(enable))


"""
Source Commands Formats
"""


def _format_source_configuration_request(source: int) -> str:
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
