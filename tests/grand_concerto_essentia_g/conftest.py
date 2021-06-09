import asyncio
import socket

import pytest

from nuvo_serial import get_nuvo, get_nuvo_async
from nuvo_serial.connection import SyncRequest, AsyncConnection
from nuvo_serial.const import MODEL_GC, MODEL_ESSENTIA_G
from nuvo_serial.grand_concerto_essentia_g import NuvoAsync, StateTrack
from nuvo_serial.message import format_message, process_message

from tests.const import SYNC_PORT_URL, ASYNC_PORT_URL, HOST
from tests.helper import find_response


@pytest.fixture(scope="session", params=[MODEL_GC, MODEL_ESSENTIA_G])
def nuvo(request):
    model = request.param
    mpatch = pytest.MonkeyPatch()
    mpatch.setattr(SyncRequest, "_process_request", mock_process_request)
    return get_nuvo(SYNC_PORT_URL, model)


async def buffer_read_for_send_message(self):
    """Fake the read from the serial device buffer by returning a response matching the
    request message."""

    if self._streaming_task.done():
        return find_response(self._message, self._model).encode() + self._eol
    else:
        await asyncio.sleep(10)


# @pytest.fixture
# def fake_buffer_read(monkeypatch):
#     monkeypatch.setattr(
#         AsyncConnection, "_read_message_from_buffer", buffer_read_for_send_message
#     )


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


# @pytest.fixture(scope="session", params=[MODEL_GC, MODEL_ESSENTIA_G])
# def all_models():
#     pass


class Input(asyncio.Protocol):
    def __init__(self):
        super().__init__()
        self._transport = None

    def connection_made(self, transport):
        self._transport = transport

    def data_received(self, data):
        self._transport.write(data)


@pytest.fixture(scope="session", params=[MODEL_GC, MODEL_ESSENTIA_G])
async def async_nuvo(request, event_loop, unused_tcp_port_factory):
    """This fixture does NOT do state tracking."""

    """pyserial-asyncio as of v0.5 does not support loop:// style ports.  It relies
    on adding writer and reader callbacks to file descriptor activity - loop://
    is impelemented by pyserial using python in memory Queues which do not have FDs.

    In order to test the lower level serial port handling code, need to create a
    listening socket for the pyserial to connect to.  This allows writes to work and
    reads will be faked with the monkeypatched _read_message_from_buffer.
    """

    _nuvo_async = None
    model = request.param
    port = unused_tcp_port_factory()
    port_url = f"socket://{HOST}:{port}"

    await event_loop.create_server(
        Input,
        HOST,
        port,
        family=socket.AF_INET,
        reuse_address=True,
        reuse_port=True,
    )

    """
    Can't use monkeypatch fixture as it's function scoped, while this fixture is
    session scoped.  Pytest runs session scope fixtures before function scoped fixtures
    meaning the monkeypatched fake_buffer_read isn't patched until after the async
    session is complete - while this works for the other request/response async tests, the
    state_tracking code makes nuvo requests during connection setup, therefore they
    fail as the real _read_message_from_buffer function is being called, not the
    monkeypatched version.

    The monkey patch fixture creates an instance of the MonkeyPatch under the hood, so
    use it here directly to skip the fixture scope resolution rules.
    """

    mpatch = pytest.MonkeyPatch()
    mpatch.setattr(
        AsyncConnection, "_read_message_from_buffer", buffer_read_for_send_message
    )

    _nuvo_async = await get_nuvo_async(
        port_url,
        model,
        do_model_check=False,
        track_state=False,
        timeout=0.1,
        disconnect_time=0.1,
    )

    yield _nuvo_async
    await _nuvo_async.disconnect()


@pytest.fixture(scope="session", params=[MODEL_GC, MODEL_ESSENTIA_G])
async def async_nuvo_groups(request, event_loop, unused_tcp_port_factory):
    """This fixture DOES do state tracking."""

    """pyserial-asyncio as of v0.5 does not support loop:// style ports.  It relies
    on adding writer and reader callbacks to file descriptor activity - loop://
    is impelemented by pyserial using python in memory Queues which do not have FDs.

    In order to test the lower level serial port handling code, need to create a
    listening socket for the pyserial to connect to.  This allows writes to work and
    reads will be faked with the monkeypatched _read_message_from_buffer.
    """

    _nuvo_async = None
    model = request.param
    port = unused_tcp_port_factory()
    ASYNC_URL = f"socket://{HOST}:{port}"

    await event_loop.create_server(
        Input,
        HOST,
        port,
        family=socket.AF_INET,
        reuse_address=True,
        reuse_port=True,
    )

    """
    Can't use monkeypatch fixture as it's function scoped, while this fixture is
    session scoped.  Pytest runs session scope fixtures before function scoped fixtures
    meaning the monkeypatched fake_buffer_read isn't patched until after the async
    session is complete - while this works for the other request/response async tests, the
    state_tracking code makes nuvo requests during connection setup, therefore they
    fail as the real _read_message_from_buffer function is being called, not the
    monkeypatched version.

    The monkey patch fixture creates an instance of the MonkeyPatch under the hood, so
    use it here directly to skip the fixture scope resolution rules.
    """
    mpatch = pytest.MonkeyPatch()
    mpatch.setattr(StateTrack, "get_initial_states", get_initial_states)

    _nuvo_async = await get_nuvo_async(
        ASYNC_URL,
        model,
        do_model_check=False,
        track_state=True,
        timeout=0.1,
        disconnect_time=0.1,
    )

    yield _nuvo_async
    await _nuvo_async.disconnect()


def mock_process_request(self, request_string):
    """Bypass process_request by returning a response matching the request."""
    return find_response(request_string, self.model)


# @pytest.fixture
# def mock_return_value(monkeypatch):
#     monkeypatch.setattr(SyncRequest, "_process_request", mock_process_request)


@pytest.fixture(scope="session")
def event_loop():
    """Override pytest-asncio's default function-scoped event_loop fixture to use
    session-scoped"""
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


async def get_initial_states(self) -> None:
    """Bypass initial state query when state tracking.
    Tests should set state_tracker._state attribute directly.
    """

    self._initial_state_retrieval_completed = True
