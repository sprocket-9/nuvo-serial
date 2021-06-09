import asyncio
from dataclasses import replace
import pytest
from tests.const import (
    SOURCE,
    SOURCE_2,
    ZONE,
    ZONE_0,
    ZONE_5,
    ZONE_6,
    ZONE_7,
    ZONE_8,
    ZONE_9,
    ZONE_10,
    ZONE_11,
    ZONE_12,
)
from nuvo_serial.message import ZoneConfiguration, ZoneEQStatus, ZoneStatus, Party
from nuvo_serial.const import (
    SYSTEM_PARTY,
    ZONE_CONFIGURATION,
    ZONE_EQ_STATUS,
    ZONE_STATUS,
    EMIT_LEVEL_NONE,
)
from nuvo_serial.grand_concerto_essentia_g import NuvoAsync, StateTrack
from unittest import mock


"""
Party host:
    zone 12
Party members
   zone 11
   zone 10

No Party set:
  zone 9

Master:
  zone 9

Slaves:
  zone 8 slaved to 9 with slave_eq=1
  zone 7 slaved to 9 with slave_eq=0

Grouped:
    Group 4:
      zone 11
      zone 10
"""

party_enabled = Party(zone=ZONE_12, party_host=True)
party_disabled = Party(zone=ZONE_0, party_host=False)

zone_baseline = ZoneConfiguration(
    zone=ZONE,
    enabled=True,
    name="XXX",
    slave_to=ZONE_0,
    group=0,
    sources=["SOURCE1", "SOURCE2", "SOURCE3", "SOURCE4", "SOURCE5", "SOURCE6"],
    exclusive_source=False,
    ir_enabled=0,
    dnd=[],
    locked=False,
    slave_eq=False,
)
zone_disabled = ZoneConfiguration(
    zone=ZONE,
    enabled=False,
    name=None,
    slave_to=None,
    group=None,
    sources=None,
    exclusive_source=None,
    ir_enabled=None,
    dnd=None,
    locked=None,
    slave_eq=None,
)
zone_party_host = replace(zone_baseline, zone=ZONE_12, name="Music Room",)
zone_12 = zone_party_host
zone_11 = replace(zone_baseline, zone=ZONE_11, name="Sun Room", group=4)
zone_10 = replace(zone_baseline, zone=ZONE_10, name="Family Room", group=4,)
zone_9_master = replace(zone_baseline, zone=ZONE_9, name="Nursery", dnd=["NOPARTY"])
zone_8 = replace(
    zone_baseline, zone=ZONE_8, name="Master Bedroom", slave_to=ZONE_9, slave_eq=True,
)
zone_7 = replace(
    zone_baseline, zone=ZONE_7, name="En Suite", slave_to=ZONE_9, slave_eq=False,
)
zone_6_disabled = replace(zone_disabled, zone=ZONE_6)
zone_5_disabled = replace(zone_disabled, zone=ZONE_5)

party_host_triggered_exclusions = {ZONE_12, ZONE_8, ZONE_7, ZONE_6, ZONE_5}
group_member_triggered_inclusions = {ZONE_10}

z_status_party_host = ZoneStatus(
    zone=ZONE_12, power=True, source=SOURCE, volume=60, mute=False, dnd=False, lock=False
)

z_status_master = ZoneStatus(
    zone=ZONE_9, power=True, source=SOURCE_2, volume=60, mute=False, dnd=False, lock=False
)

z_11_group_member_status_post = ZoneStatus(
    zone=ZONE_11, power=True, source=SOURCE_2, volume=55, mute=False, dnd=False, lock=False
)

z_10_group_member_status_post = ZoneStatus(
    zone=ZONE_10, power=True, source=SOURCE_2, volume=32, mute=False, dnd=False, lock=False
)

z_eq_master = ZoneEQStatus(
    zone=ZONE_9, bass=18, treble=-4, loudcmp=True, balance_position="R", balance=9
)

z_eq_slave = ZoneEQStatus(
    zone=ZONE_8, bass=0, treble=8, loudcmp=True, balance_position="L", balance=1
)

PARTY_MODE = "party_mode"
NO_PARTY_MODE = "no_party_mode"


@pytest.fixture
def get_initial_state():
    def _get_state(mode):
        if mode == PARTY_MODE:
            return {
                SYSTEM_PARTY: {"system": party_enabled},
                ZONE_CONFIGURATION: {
                    12: zone_party_host,
                    11: zone_11,
                    10: zone_10,
                    9: zone_9_master,
                    8: zone_8,
                    7: zone_7,
                    6: zone_6_disabled,
                    5: zone_5_disabled,
                },
            }
        elif mode == NO_PARTY_MODE:
            return {
                SYSTEM_PARTY: {"system": party_disabled},
                ZONE_CONFIGURATION: {
                    12: zone_12,
                    11: zone_11,
                    10: zone_10,
                    9: zone_9_master,
                    8: zone_8,
                    7: zone_7,
                    6: zone_6_disabled,
                    5: zone_5_disabled,
                },
            }

    return _get_state

# mock representing an external listener callback
external_listener_cb = mock.AsyncMock()


# mock for nuvo_serial.grand_concerto_essentia_g.StateTrack._get_zone_states method
zone_states_mock_for_source_groups = mock.AsyncMock(
    return_value=[z_10_group_member_status_post]
)


@pytest.mark.asyncio
class TestAsyncGroupTracking:
    """Tests for state tracking and the various nuvo groups tracking

    Tests:
        Party mode
        Master Slave mode ZoneStatus changes
        Master Slave mode ZoneEQStatus changes
        Groups - zone groups that mirror changes in Source selection

    This tracking code runs as asyncio task callbacks on reception of Nuvo messages.
    This is difficult to test so call the callback directly with an appropriate
    nuvo message to trigger the group handler.
    """

    @mock.patch("nuvo_serial.grand_concerto_essentia_g.StateTrack._get_zone_states")
    async def test_async_group_party(
        self, get_zone_states, async_nuvo_groups, get_initial_state
    ):
        """Send a Party host ZoneStatus msg and ensure the correct list of zones
        get a ZoneStatus query.
        """
        self.set_initial_state(async_nuvo_groups, get_initial_state(PARTY_MODE))
        # Send Party host ZoneStatus
        message = {"event_name": ZONE_STATUS, "event": z_status_party_host}
        await async_nuvo_groups._state_tracker._state_tracker(message)

        # Sleep to allow get_zone_states to execute
        await asyncio.sleep(0.1)

        # Check get_zones states is called with the correct zone list
        get_zone_states.assert_awaited()
        get_zone_states.assert_called_with(exclusions=party_host_triggered_exclusions)

    @mock.patch("nuvo_serial.grand_concerto_essentia_g.StateTrack._get_zone_states")
    async def test_async_group_master_slave(
        self, get_zone_states, async_nuvo_groups, get_initial_state
    ):
        """Send a Master ZoneStatus msg and ensure mirrored ZoneStatus msgs are
        emitted to external listener.
        """
        async_nuvo_groups.add_subscriber(external_listener_cb, ZONE_STATUS)
        self.set_initial_state(async_nuvo_groups, get_initial_state(NO_PARTY_MODE))
        external_listener_cb.reset_mock()

        # Send Master ZoneStatus
        message = {"event_name": ZONE_STATUS, "event": z_status_master}
        await async_nuvo_groups._state_tracker._state_tracker(message)

        # Sleep to allow external callbacks to execute
        await asyncio.sleep(0.1)

        # Check external callback
        assert external_listener_cb.call_count == 2

        z_8_slave_result = replace(z_status_master, zone=ZONE_8)
        z_7_slave_result = replace(z_status_master, zone=ZONE_7)
        expected_cb_calls = [
            mock.call({"event_name": ZONE_STATUS, "event": z_8_slave_result}),
            mock.call({"event_name": ZONE_STATUS, "event": z_7_slave_result}),
        ]
        external_listener_cb.assert_has_calls(expected_cb_calls, any_order=True)

        # Check local state is updated
        assert (
            async_nuvo_groups._state_tracker._state[ZONE_STATUS][ZONE_8]
            == z_8_slave_result
        )
        assert (
            async_nuvo_groups._state_tracker._state[ZONE_STATUS][ZONE_7]
            == z_7_slave_result
        )

    @mock.patch(
        "nuvo_serial.grand_concerto_essentia_g.StateTrack._get_zone_states",
        new=zone_states_mock_for_source_groups,
    )
    async def test_async_group_source_groups(
        self, async_nuvo_groups, get_initial_state
    ):
        """Send a grouped zone's ZoneStatus msg and ensure the other grouped zones
        ZoneStatus msgs are emitted to external listener.
        """
        async_nuvo_groups.add_subscriber(external_listener_cb, ZONE_STATUS)
        self.set_initial_state(
            async_nuvo_groups, get_initial_state(NO_PARTY_MODE)
        )
        external_listener_cb.reset_mock()

        # Send a grouped zone's ZoneStatus with a change of source
        message = {"event_name": ZONE_STATUS, "event": z_11_group_member_status_post}
        await async_nuvo_groups._state_tracker._state_tracker(message)
        await asyncio.sleep(0.1)
        # Check get_zones states is called with the correct zone list
        zone_states_mock_for_source_groups.assert_awaited()
        zone_states_mock_for_source_groups.assert_called_with(
            inclusions=group_member_triggered_inclusions, emit_level=EMIT_LEVEL_NONE
        )
        # Check external callback
        assert external_listener_cb.call_count == 1

        expected_cb_calls = [
            mock.call(
                {"event_name": ZONE_STATUS, "event": z_10_group_member_status_post}
            )
        ]
        external_listener_cb.assert_has_calls(expected_cb_calls, any_order=True)

        # Check local state is updated
        assert (
            async_nuvo_groups._state_tracker._state[ZONE_STATUS][ZONE_11]
            == z_11_group_member_status_post
        )
        assert (
            async_nuvo_groups._state_tracker._state[ZONE_STATUS][ZONE_10]
            == z_10_group_member_status_post
        )

    async def test_async_group_master_slave_eq(
        self, async_nuvo_groups, get_initial_state
    ):
        """Send a Master zone's ZoneEQStatus msg and ensure slaved zones with
        slave_eq=1 are emitted to external listener.
        """
        async_nuvo_groups.add_subscriber(external_listener_cb, ZONE_EQ_STATUS)
        self.set_initial_state(async_nuvo_groups, get_initial_state(NO_PARTY_MODE))
        external_listener_cb.reset_mock()

        # Send Master ZoneStatus
        message = {"event_name": ZONE_EQ_STATUS, "event": z_eq_master}
        await async_nuvo_groups._state_tracker._state_tracker(message)
        # Sleep to allow external callbacks to execute
        await asyncio.sleep(0.1)
        assert external_listener_cb.call_count == 1

        # Check external callback
        z_8_slave_result = replace(z_eq_master, zone=ZONE_8)
        expected_cb_calls = [
            mock.call({"event_name": ZONE_EQ_STATUS, "event": z_8_slave_result}),
        ]
        external_listener_cb.assert_has_calls(expected_cb_calls, any_order=True)
        assert (
            async_nuvo_groups._state_tracker._state[ZONE_EQ_STATUS][ZONE_8]
            == z_8_slave_result
        )

    async def test_async_group_slave_slave_eq(
        self, async_nuvo_groups, get_initial_state
    ):
        """Send a Slave zone's ZoneEQStatus msg and ensure slaved zones with
        slave_eq=1 and the master zone's ZoneEQStatus are emitted to external listener.
        """
        async_nuvo_groups.add_subscriber(external_listener_cb, ZONE_EQ_STATUS)
        self.set_initial_state(async_nuvo_groups, get_initial_state(NO_PARTY_MODE))
        external_listener_cb.reset_mock()

        # Send Master ZoneStatus
        message = {"event_name": ZONE_EQ_STATUS, "event": z_eq_slave}
        await async_nuvo_groups._state_tracker._state_tracker(message)
        # Sleep to allow external callbacks to execute
        await asyncio.sleep(0.1)
        print(external_listener_cb.call_args_list)
        assert external_listener_cb.call_count == 1

        # Check external callback
        z_9_master_result = replace(z_eq_slave, zone=ZONE_9)
        expected_cb_calls = [
            mock.call({"event_name": ZONE_EQ_STATUS, "event": z_9_master_result}),
        ]
        external_listener_cb.assert_has_calls(expected_cb_calls, any_order=True)
        assert (
            async_nuvo_groups._state_tracker._state[ZONE_EQ_STATUS][ZONE_9]
            == z_9_master_result
        )

    def set_initial_state(self, nuvo, state):
        nuvo._state_tracker._state = state
