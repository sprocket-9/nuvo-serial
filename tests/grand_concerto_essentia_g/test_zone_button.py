from dataclasses import asdict, replace
import pytest
from tests.const import SOURCE, ZONE, ZONE_OFF, ZONE_NUVONET_SOURCE
from nuvo_serial.message import ZoneButton, ZoneStatus, OKResponse
from nuvo_serial.const import (
    ZONE_BUTTON_PLAY_PAUSE,
    ZONE_BUTTON_PREV,
    ZONE_BUTTON_NEXT
)


button_baseline = ZoneButton(
    zone=ZONE,
    source=SOURCE,
    button=ZONE_BUTTON_PLAY_PAUSE,
)

button_prev = replace(button_baseline, button=ZONE_BUTTON_PREV)
button_next = replace(button_baseline, button=ZONE_BUTTON_NEXT)

zone_off_baseline = ZoneStatus(
    zone=ZONE_OFF,
    power=False
)

response_ok = OKResponse(ok_response=True)


@pytest.mark.asyncio
@pytest.mark.usefixtures("fake_buffer_read", "all_models")
class TestAsyncZoneConfiguration:
    async def test_async_zone_button_play_pause(self, async_nuvo):
        response = await async_nuvo.zone_button_play_pause(ZONE)
        assert asdict(response) == asdict(button_baseline)

    async def test_async_zone_button_prev(self, async_nuvo):
        response = await async_nuvo.zone_button_prev(ZONE)
        assert asdict(response) == asdict(button_prev)

    async def test_async_zone_button_next(self, async_nuvo):
        response = await async_nuvo.zone_button_next(ZONE)
        assert asdict(response) == asdict(button_next)

    async def test_async_zone_button_play_pause_zone_off(self, async_nuvo):
        response = await async_nuvo.zone_button_play_pause(ZONE_OFF)
        assert asdict(response) == asdict(zone_off_baseline)

    async def test_async_zone_button_prev_zone_off(self, async_nuvo):
        response = await async_nuvo.zone_button_prev(ZONE_OFF)
        assert asdict(response) == asdict(zone_off_baseline)

    async def test_async_zone_button_next_zone_off(self, async_nuvo):
        response = await async_nuvo.zone_button_next(ZONE_OFF)
        assert asdict(response) == asdict(zone_off_baseline)

    async def test_async_zone_button_play_pause_nuvonet_source(self, async_nuvo):
        response = await async_nuvo.zone_button_play_pause(ZONE_NUVONET_SOURCE)
        assert asdict(response) == asdict(response_ok)

    async def test_async_zone_button_prev_nuvonet_source(self, async_nuvo):
        response = await async_nuvo.zone_button_prev(ZONE_NUVONET_SOURCE)
        assert asdict(response) == asdict(response_ok)

    async def test_async_zone_button_next_nuvonet_source(self, async_nuvo):
        response = await async_nuvo.zone_button_next(ZONE_NUVONET_SOURCE)
        assert asdict(response) == asdict(response_ok)
