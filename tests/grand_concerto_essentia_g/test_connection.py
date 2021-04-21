import asyncio
from dataclasses import asdict, replace
import pytest
from serial import SerialException
from tests.const import ZONE
from nuvo_serial.connection import SyncRequest, AsyncConnection
from nuvo_serial.exceptions import (
    MessageClassificationError,
    MessageFormatError,
    MessageResponseError,
)
from tests.helper import find_response

def call_counter():
    num = 0
    yield num
    num += 1
    yield num


async def buffer_read_timeout(self):
    await asyncio.sleep(0.2)


async def buffer_read_serial_exception(self):
    raise SerialException


async def mock_read_message_from_buffer(self):
    pass


@pytest.fixture
def async_mock_buffer_read(monkeypatch):
    monkeypatch.setattr(
        AsyncConnection, "_read_message_from_buffer", mock_read_message_from_buffer
    )


@pytest.mark.asyncio
class TestAsyncConnection:

    async def test_async_response_timeout(self, monkeypatch, async_nuvo):
        monkeypatch.setattr(
            AsyncConnection, "_read_message_from_buffer", buffer_read_timeout
        )
        with pytest.raises(MessageResponseError):
            await async_nuvo.zone_configuration(ZONE)

    async def test_async_response_serial_error(self, monkeypatch, async_nuvo):
        """Ensure the _reconnect task runs when a SerialException occurs."""

        monkeypatch.setattr(
            AsyncConnection, "_read_message_from_buffer", buffer_read_serial_exception
        )

        f_connected = asyncio.get_running_loop().create_future()

        """This will run as a task in place of the real _reconnect task."""
        async def mock_reconnect(self):
            f_connected.set_result("connected")

        monkeypatch.setattr(AsyncConnection, "_reconnect", mock_reconnect)

        try:
            await async_nuvo.zone_configuration(ZONE)
        except MessageResponseError:
            """A MessageResponseError will be raised so the caller will know
            the command failed - the lib will then do a _reconnect"""

            """If mock_reconnect isn't called this test will fail with a raised
            asyncio.exceptions.TimeoutError."""
            await asyncio.wait_for(f_connected, 0.1)
            assert f_connected.result() == "connected"
