from dataclasses import asdict, replace
import pytest
from tests.const import ZONE, SOURCE
from nuvo_serial.message import ZoneStatus


zone_baseline = ZoneStatus(
    zone=ZONE, power=True, source=SOURCE, volume=60, mute=False, dnd=False, lock=False
)

zone_off = replace(
    zone_baseline, power=False, source=None, volume=None, mute=None, dnd=None, lock=None
)
zone_source_change = replace(zone_baseline, source=5,)
zone_set_source = zone_source_change
zone_mute_on = replace(zone_baseline, volume=None, mute=True)
zone_mute_off = zone_baseline
zone_volume_up = replace(zone_baseline, volume=59)
zone_dnd_on = replace(zone_baseline, dnd=True)
zone_dnd_off = zone_baseline


@pytest.mark.usefixtures("mock_return_value")
class TestZoneStatus:
    def test_zone_status(self, nuvo):
        response = nuvo.zone_status(ZONE)
        assert asdict(response) == asdict(zone_baseline)

    def test_zone_set_power(self, nuvo):
        response = nuvo.set_power(ZONE, False)
        assert asdict(response) == asdict(zone_off)

    def test_zone_set_source(self, nuvo):
        response = nuvo.set_source(ZONE, 5)
        assert asdict(response) == asdict(zone_set_source)

    def test_zone_set_next_source(self, nuvo):
        response = nuvo.set_next_source(ZONE)
        assert asdict(response) == asdict(zone_source_change)

    def test_zone_set_mute_on(self, nuvo):
        response = nuvo.set_mute(ZONE, True)
        assert asdict(response) == asdict(zone_mute_on)

    def test_zone_set_mute_off(self, nuvo):
        response = nuvo.set_mute(ZONE, False)
        assert asdict(response) == asdict(zone_mute_off)

    def test_zone_set_volume(self, nuvo):
        response = nuvo.set_volume(ZONE, 59)
        assert asdict(response) == asdict(zone_volume_up)

    def test_zone_dnd_on(self, nuvo):
        response = nuvo.set_dnd(ZONE, True)
        assert asdict(response) == asdict(zone_dnd_on)

    def test_zone_dnd_off(self, nuvo):
        response = nuvo.set_dnd(ZONE, False)
        assert asdict(response) == asdict(zone_dnd_off)


@pytest.mark.asyncio
@pytest.mark.usefixtures("fake_buffer_read")
class TestAsyncZoneStatus:
    async def test_async_zone_status(self, async_nuvo):
        response = await async_nuvo.zone_status(ZONE)
        assert asdict(response) == asdict(zone_baseline)

    async def test_async_zone_set_power(self, async_nuvo):
        response = await async_nuvo.set_power(ZONE, False)
        assert asdict(response) == asdict(zone_off)

    async def test_async_zone_set_source(self, async_nuvo):
        response = await async_nuvo.set_source(ZONE, 5)
        assert asdict(response) == asdict(zone_set_source)

    async def test_async_zone_set_next_source(self, async_nuvo):
        response = await async_nuvo.set_next_source(ZONE)
        assert asdict(response) == asdict(zone_source_change)

    async def test_async_zone_set_mute_on(self, async_nuvo):
        response = await async_nuvo.set_mute(ZONE, True)
        assert asdict(response) == asdict(zone_mute_on)

    async def test_async_zone_set_mute_off(self, async_nuvo):
        response = await async_nuvo.set_mute(ZONE, False)
        assert asdict(response) == asdict(zone_mute_off)

    async def test_async_zone_set_volume(self, async_nuvo):
        response = await async_nuvo.set_volume(ZONE, 59)
        assert asdict(response) == asdict(zone_volume_up)

    async def test_async_zone_dnd_on(self, async_nuvo):
        response = await async_nuvo.set_dnd(ZONE, True)
        assert asdict(response) == asdict(zone_dnd_on)

    async def test_async_zone_dnd_off(self, async_nuvo):
        response = await async_nuvo.set_dnd(ZONE, False)
        assert asdict(response) == asdict(zone_dnd_off)
