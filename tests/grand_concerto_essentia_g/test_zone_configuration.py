from dataclasses import asdict, replace
import pytest
from tests.const import ZONE, ZONE_MASTER
from nuvo_serial.message import ZoneConfiguration


zone_baseline = ZoneConfiguration(
    zone=ZONE,
    enabled=True,
    name="Kitchen",
    slave_to=0,
    group=0,
    sources=['SOURCE1', 'SOURCE5'],
    exclusive_source=False,
    ir_enabled=0,
    dnd=['NOMUTE', 'NOPAGE', 'NOPARTY'],
    locked=False,
    slave_eq=0
)

zone_sources = replace(zone_baseline, sources=['SOURCE6'])
zone_dnd = replace(zone_baseline, dnd=['NOMUTE'])
zone_name = replace(zone_baseline, name="Office")
zone_slave_to = replace(zone_baseline, slave_to=ZONE_MASTER)


@pytest.mark.usefixtures("mock_return_value")
class TestZoneConfiguration:
    def test_zone_configuration(self, nuvo):
        response = nuvo.zone_configuration(ZONE)
        assert asdict(response) == asdict(zone_baseline)

    def test_zone_configuration_set_source_mask(self, nuvo):
        response = nuvo.zone_set_source_mask(ZONE, ['SOURCE6'])
        assert asdict(response) == asdict(zone_sources)

    def test_zone_configuration_set_dnd_mask(self, nuvo):
        response = nuvo.zone_set_dnd_mask(ZONE, ['NOMUTE'])
        assert asdict(response) == asdict(zone_dnd)

    def test_zone_configuration_set_name(self, nuvo):
        response = nuvo.zone_set_name(ZONE, "Office")
        assert asdict(response) == asdict(zone_name)

    def test_zone_configuration_slave_to(self, nuvo):
        response = nuvo.zone_slave_to(ZONE, ZONE_MASTER)
        assert asdict(response) == asdict(zone_slave_to)


@pytest.mark.asyncio
@pytest.mark.usefixtures("fake_buffer_read", "all_models")
class TestAsyncZoneConfiguration:
    async def test_async_zone_configuration(self, async_nuvo):
        response = await async_nuvo.zone_configuration(ZONE)
        assert asdict(response) == asdict(zone_baseline)

    async def test_async_zone_configuration_set_source_mask(self, async_nuvo):
        response = await async_nuvo.zone_set_source_mask(ZONE, ['SOURCE6'])
        assert asdict(response) == asdict(zone_sources)

    async def test_async_zone_configuration_set_dnd_mask(self, async_nuvo):
        response = await async_nuvo.zone_set_dnd_mask(ZONE, ['NOMUTE'])
        assert asdict(response) == asdict(zone_dnd)

    async def test_async_zone_configuration_set_name(self, async_nuvo):
        response = await async_nuvo.zone_set_name(ZONE, "Office")
        assert asdict(response) == asdict(zone_name)

    async def test_async_zone_configuration_slave_to(self, async_nuvo):
        response = await async_nuvo.zone_slave_to(ZONE, ZONE_MASTER)
        assert asdict(response) == asdict(zone_slave_to)
