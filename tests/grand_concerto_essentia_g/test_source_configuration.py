from dataclasses import asdict, replace
import pytest
from tests.const import SOURCE
from nuvo_serial.message import SourceConfiguration


source_baseline = SourceConfiguration(
    source=SOURCE,
    enabled=True,
    name="Network Streamer",
    gain=4,
    nuvonet_source=False,
    short_name="NST",
)

source_disabled = SourceConfiguration(
    source=SOURCE,
    enabled=False,
    name=None,
    gain=None,
    nuvonet_source=None,
    short_name=None,
)

source_long_name = replace(source_baseline, name="Music Server")
source_disable = source_disabled
source_gain = replace(source_baseline, gain=8)
source_nuvonet = replace(source_baseline, nuvonet_source=1)
source_short_name = replace(source_baseline, short_name="ABC")


@pytest.mark.usefixtures("mock_return_value")
class TestSourceConfiguration:
    def test_source_configuration_status(self, nuvo):
        response = nuvo.source_status(SOURCE)
        assert asdict(response) == asdict(source_baseline)

    def test_source_configuration_set_name(self, nuvo):
        response = nuvo.set_source_name(SOURCE, "Music Server")
        assert asdict(response) == asdict(source_long_name)

    def test_source_configuration_set_source_enable(self, nuvo):
        response = nuvo.set_source_enable(SOURCE, False)
        assert asdict(response) == asdict(source_disable)

    def test_source_configuration_set_nuvonet(self, nuvo):
        response = nuvo.set_source_nuvonet(SOURCE, True)
        assert asdict(response) == asdict(source_nuvonet)

    def test_source_configuration_set_short_name(self, nuvo):
        response = nuvo.set_source_shortname(SOURCE, "ABC")
        assert asdict(response) == asdict(source_short_name)


@pytest.mark.usefixtures("fake_buffer_read", "all_models")
@pytest.mark.asyncio
class TestAsyncSourceConfiguration:

    async def test_async_source_configuration_status(self, async_nuvo):
        response = await async_nuvo.source_status(SOURCE)
        assert asdict(response) == asdict(source_baseline)

    async def test_async_source_configuration_set_name(self, async_nuvo):
        response = await async_nuvo.set_source_name(SOURCE, "Music Server")
        assert asdict(response) == asdict(source_long_name)

    async def test_async_source_configuration_set_source_enable(self, async_nuvo):
        response = await async_nuvo.set_source_enable(SOURCE, False)
        assert asdict(response) == asdict(source_disable)

    async def test_async_source_configuration_set_nuvonet(self, async_nuvo):
        response = await async_nuvo.set_source_nuvonet(SOURCE, True)
        assert asdict(response) == asdict(source_nuvonet)

    async def test_async_source_configuration_set_short_name(self, async_nuvo):
        response = await async_nuvo.set_source_shortname(SOURCE, "ABC")
        assert asdict(response) == asdict(source_short_name)
