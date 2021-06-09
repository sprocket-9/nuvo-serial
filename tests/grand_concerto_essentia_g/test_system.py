from dataclasses import asdict
import pytest
from tests.const import ZONE
from nuvo_serial.message import Party


party_host = Party(zone=ZONE, party_host=True)

class TestZoneConfiguration:
    def test_set_party_host(self, nuvo):
        response = nuvo.set_party_host(ZONE, True)
        assert asdict(response) == asdict(party_host)


@pytest.mark.asyncio
class TestAsyncZoneConfiguration:
    async def test_async_set_party_host(self, async_nuvo):
        response = await async_nuvo.set_party_host(ZONE, True)
        assert asdict(response) == asdict(party_host)
