from dataclasses import asdict, replace
import pytest
from tests.const import ZONE
from nuvo_serial.message import ZoneEQStatus


zone_baseline = ZoneEQStatus(
    zone=ZONE, bass=18, treble=-4, loudcmp=True, balance_position='R', balance=9
)

zone_bass = replace(zone_baseline, bass=-12)
zone_treble = replace(zone_baseline, treble=8)
zone_balance_L = replace(zone_baseline, balance_position='L', balance=10)
zone_balance_R = replace(zone_baseline, balance_position='R', balance=2)
zone_balance_C = replace(zone_baseline, balance_position='C', balance=0)
zone_loudcmp = replace(zone_baseline, loudcmp=False)


class TestZoneEQ:
    def test_zone_eq_status(self, nuvo):
        response = nuvo.zone_eq_status(ZONE)
        assert asdict(response) == asdict(zone_baseline)

    def test_zone_eq_set_bass(self, nuvo):
        response = nuvo.set_bass(ZONE, -12)
        assert asdict(response) == asdict(zone_bass)

    def test_zone_eq_set_treble(self, nuvo):
        response = nuvo.set_treble(ZONE, 8)
        assert asdict(response) == asdict(zone_treble)

    def test_zone_eq_set_balance_L(self, nuvo):
        response = nuvo.set_balance(ZONE, 'L', 10)
        assert asdict(response) == asdict(zone_balance_L)

    def test_zone_eq_set_balance_R(self, nuvo):
        response = nuvo.set_balance(ZONE, 'R', 2)
        assert asdict(response) == asdict(zone_balance_R)

    def test_zone_eq_set_balance_C(self, nuvo):
        response = nuvo.set_balance(ZONE, 'C', 0)
        assert asdict(response) == asdict(zone_balance_C)

    def test_zone_eq_set_loudcmp(self, nuvo):
        response = nuvo.set_loudness_comp(ZONE, False)
        assert asdict(response) == asdict(zone_loudcmp)


@pytest.mark.asyncio
class TestAsyncZoneEQ:
    async def test_async_zone_eq_status(self, async_nuvo):
        response = await async_nuvo.zone_eq_status(ZONE)
        assert asdict(response) == asdict(zone_baseline)

    async def test_async_zone_eq_set_bass(self, async_nuvo):
        response = await async_nuvo.set_bass(ZONE, -12)
        assert asdict(response) == asdict(zone_bass)

    async def test_async_zone_eq_set_treble(self, async_nuvo):
        response = await async_nuvo.set_treble(ZONE, 8)
        assert asdict(response) == asdict(zone_treble)

    async def test_async_zone_eq_set_balance_L(self, async_nuvo):
        response = await async_nuvo.set_balance(ZONE, 'L', 10)
        assert asdict(response) == asdict(zone_balance_L)

    async def test_async_zone_eq_set_balance_R(self, async_nuvo):
        response = await async_nuvo.set_balance(ZONE, 'R', 2)
        assert asdict(response) == asdict(zone_balance_R)

    async def test_async_zone_eq_set_balance_C(self, async_nuvo):
        response = await async_nuvo.set_balance(ZONE, 'C', 0)
        assert asdict(response) == asdict(zone_balance_C)

    async def test_async_zone_eq_set_loudcmp(self, async_nuvo):
        response = await async_nuvo.set_loudness_comp(ZONE, False)
        assert asdict(response) == asdict(zone_loudcmp)
