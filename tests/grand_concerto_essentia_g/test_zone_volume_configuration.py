from dataclasses import asdict, replace
import pytest
from tests.const import ZONE
from nuvo_serial.message import ZoneVolumeConfiguration


zone_baseline = ZoneVolumeConfiguration(
    zone=ZONE, max_vol=0, ini_vol=20, page_vol=40, party_vol=50, vol_rst=False
)

zone_max = replace(zone_baseline, max_vol=22)
zone_initial = replace(zone_baseline, ini_vol=33)
zone_page = replace(zone_baseline, page_vol=44)
zone_party = replace(zone_baseline, party_vol=55)
zone_reset = replace(zone_baseline, vol_rst=True)


class TestZoneVolumeConfiguration:
    def test_zone_volume_configuration(self, nuvo):
        response = nuvo.zone_volume_configuration(ZONE)
        assert asdict(response) == asdict(zone_baseline)

    def test_zone_volume_max(self, nuvo):
        response = nuvo.zone_volume_max(ZONE, 22)
        assert asdict(response) == asdict(zone_max)

    def test_zone_volume_ini(self, nuvo):
        response = nuvo.zone_volume_initial(ZONE, 33)
        assert asdict(response) == asdict(zone_initial)

    def test_zone_volume_page(self, nuvo):
        response = nuvo.zone_volume_page(ZONE, 44)
        assert asdict(response) == asdict(zone_page)

    def test_zone_volume_party(self, nuvo):
        response = nuvo.zone_volume_party(ZONE, 55)
        assert asdict(response) == asdict(zone_party)

    def test_zone_volume_reset(self, nuvo):
        response = nuvo.zone_volume_reset(ZONE, True)
        assert asdict(response) == asdict(zone_reset)


@pytest.mark.asyncio
class TestAsyncZoneVolumeConfiguration:
    async def test_async_zone_volume_configuration(self, async_nuvo):
        response = await async_nuvo.zone_volume_configuration(ZONE)
        assert asdict(response) == asdict(zone_baseline)

    async def test_async_zone_volume_max(self, async_nuvo):
        response = await async_nuvo.zone_volume_max(ZONE, 22)
        assert asdict(response) == asdict(zone_max)

    async def test_async_zone_volume_ini(self, async_nuvo):
        response = await async_nuvo.zone_volume_initial(ZONE, 33)
        assert asdict(response) == asdict(zone_initial)

    async def test_async_zone_volume_page(self, async_nuvo):
        response = await async_nuvo.zone_volume_page(ZONE, 44)
        assert asdict(response) == asdict(zone_page)

    async def test_async_zone_volume_party(self, async_nuvo):
        response = await async_nuvo.zone_volume_party(ZONE, 55)
        assert asdict(response) == asdict(zone_party)

    async def test_async_zone_volume_reset(self, async_nuvo):
        response = await async_nuvo.zone_volume_reset(ZONE, True)
        assert asdict(response) == asdict(zone_reset)
