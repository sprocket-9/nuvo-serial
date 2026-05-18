from dataclasses import asdict

import pytest

from nuvo_serial.message import SourceDisplayTrack
from tests.const import SOURCE


TRACK_DURATION = 240
TRACK_POSITION = 17
TRACK_STATUS = 1

source_display_track = SourceDisplayTrack(
    source=SOURCE,
    track_duration=TRACK_DURATION,
    track_position=TRACK_POSITION,
    status=TRACK_STATUS,
)


@pytest.mark.asyncio
class TestAsyncSourceDisplayTrack:
    async def test_async_set_source_display_track(self, async_nuvo):
        response = await async_nuvo.set_source_display_track(
            SOURCE, TRACK_DURATION, TRACK_POSITION, TRACK_STATUS
        )

        assert asdict(response) == asdict(source_display_track)
