import asyncio
import socket

import pytest

from nuvo_serial import get_nuvo, get_nuvo_async
from nuvo_serial.connection import SyncRequest, AsyncConnection
from nuvo_serial.const import MODEL_GC
from nuvo_serial.grand_concerto_essentia_g import NuvoAsync
from nuvo_serial.message import format_message, process_message

from tests.const import SYNC_PORT_URL, ASYNC_PORT_URL
from tests.helper import find_response


MODEL = MODEL_GC
HOST = "127.0.0.1"
PORT = 63321


@pytest.fixture
def nuvo():
    return get_nuvo(SYNC_PORT_URL, MODEL)


async def buffer_read_for_send_message(self):
    """Fake the read from the serial device buffer by returning a response matching the
    request message."""
    if self._streaming_task.done():
        return find_response(self._message, self._model).encode() + self._eol
    else:
        await asyncio.sleep(10)


@pytest.fixture
def fake_buffer_read(monkeypatch):
    monkeypatch.setattr(
        AsyncConnection, "_read_message_from_buffer", buffer_read_for_send_message
    )


# async def version(self):
#     """Decided to put a do_model_check option in get_nuvo_async to allow skipping
#     model version check.  As the function scoped monkeypatch fixture is no longer used
#     in async_nuvo fixture, this allowed to use session scope, meaning the socket
#     setup was only ran once per session rather than the (slow) once per test method."""

#     """Fake the get_version method.  This allows monkeypatching
#     _read_message_from_buffer for everything AFTER the model version check which
#     happens at connect() time."""

#     response = find_response("VER", MODEL)
#     return process_message(MODEL, response.encode())[1]


# @pytest.fixture
# def fake_version(monkeypatch):
#     monkeypatch.setattr(NuvoAsync, "get_version", version)


@pytest.fixture(scope="session")
async def async_nuvo(event_loop, async_disconnect):
    """pyserial-asyncio as of v0.5 does not support loop:// style ports.  It relies
    on adding writer and reader callbacks to file descriptor activity - loop://
    is impelemented by pyserial using python in memory Queues which do not have FDs.

    In order to test the lower level serial port handling code, need to create a
    listening socket for the pyserial to connect to.  This allows writes to work and
    reads will be faked with the monkeypatched _read_message_from_buffer.
    """

    if ASYNC_PORT_URL.startswith("socket://"):

        class Input(asyncio.Protocol):
            def __init__(self):
                super().__init__()
                self._transport = None

            def connection_made(self, transport):
                self._transport = transport

            def data_received(self, data):
                self._transport.write(data)

        # class Output(asyncio.Protocol):

        #     def __init__(self):
        #         super().__init__()
        #         self._transport = None

        #     def connection_made(self, transport):
        #         self._transport = transport
        #         actions.append('open')
        #         transport.write(TEXT)

        #     def data_received(self, data):
        #         received.append(data)
        #         if b'\n' in data:
        #             self._transport.close()

        #     def connection_lost(self, exc):
        #         actions.append('close')
        #         self._transport.loop.stop()

        #     def pause_writing(self):
        #         actions.append('pause')
        #         print(self._transport.get_write_buffer_size())

        #     def resume_writing(self):
        #         actions.append('resume')
        #         print(self._transport.get_write_buffer_size())

        await event_loop.create_server(
            Input,
            HOST,
            PORT,
            family=socket.AF_INET,
            reuse_address=True,
            reuse_port=True,
        )

    global _nuvo_async
    _nuvo_async = await get_nuvo_async(
        ASYNC_PORT_URL, MODEL, do_model_check=False, track_state=False, timeout=0.1, disconnect_time=0.1
    )
    return _nuvo_async


@pytest.fixture(scope="session")
async def async_disconnect():
    """This will be autoused for sync and async and will fail if running a subset
    of tests which d not contain an async test which uses the async_nuvo fixture.
    """

    yield 1
    await _nuvo_async.disconnect()


def mock_process_request(cls, request_string):
    """Bypass process_request by returning a response matching the request."""
    return find_response(request_string, MODEL)


@pytest.fixture
def mock_return_value(monkeypatch):
    monkeypatch.setattr(SyncRequest, "_process_request", mock_process_request)


@pytest.fixture(scope="session")
def event_loop():
    """Override pytest-asncio's default function-scoped event_loop fixture to use
    session-scoped"""
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


async def mock_send_message(self, msg, message_types):
    """Bypass send_message by returning a response matching the request."""
    response = find_response(msg, MODEL)
    return process_message(MODEL, response.encode())[1]


@pytest.fixture
def async_mock_return_value(monkeypatch):
    monkeypatch.setattr(AsyncConnection, "send_message", mock_send_message)


# async def mock_connect(self):
#     pass


# @pytest.fixture
# def async_mock_connect(monkeypatch):
#     """Only needed to prevent the "Task was destroyed but it is pending" Exception
#     being raised at the end of the tests due to the streaming_reader task still
#     running
#     """
#     monkeypatch.setattr(AsyncConnection, "connect", mock_connect)
