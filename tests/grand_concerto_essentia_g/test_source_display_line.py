from dataclasses import asdict

import pytest

from nuvo_serial.message import SourceDisplayLine
from tests.const import SOURCE


SOURCE_DISPLAY_LINE = 1
SOURCE_DISPLAY_TEXT = "Music Server"

source_display_line = SourceDisplayLine(
    source=SOURCE,
    line=SOURCE_DISPLAY_LINE,
    text=SOURCE_DISPLAY_TEXT,
)


@pytest.mark.asyncio
class TestAsyncSourceDisplayLine:
    async def test_async_set_source_display_line(self, async_nuvo):
        response = await async_nuvo.set_source_display_line(
            SOURCE, SOURCE_DISPLAY_LINE, SOURCE_DISPLAY_TEXT
        )

        assert asdict(response) == asdict(source_display_line)
