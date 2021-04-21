from __future__ import annotations

import asyncio
from asyncio.exceptions import IncompleteReadError, LimitOverrunError, TimeoutError

import serial_asyncio
import logging
import re
import serial  # type: ignore
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Literal,
    Optional,
    overload,
    Match,
    Tuple,
    Type,
    TypeVar,
    Union,
)
from functools import wraps
from threading import RLock
import time
from serial import SerialException
from nuvo_serial.configuration import config
from nuvo_serial.exceptions import (
    MessageClassificationError,
    MessageFormatError,
    MessageResponseError,
)

from nuvo_serial.message import (
    format_message,
    process_message,
    SourceConfiguration,
    ZoneAllOff,
    ZoneButton,
    ZoneConfiguration,
    ZoneEQStatus,
    ZoneStatus,
    ZoneVolumeConfiguration,
    Version,
    NuvoClass,
)
from nuvo_serial.nuvo_typing import NuvoMsgType


_LOGGER = logging.getLogger(__name__)

REQUEST_RETRIES = 0  # Retries to attempt when an invalid response is received
REQUEST_RETRY_DELAY = 1  # Delay in seconds between request retries
TIMEOUT_OP = 0.2  # Number of seconds before serial operation timeout
TIMEOUT_RESPONSE = 1.0  # Number of seconds before command response timeout
DISCONNECT_TIME = 2


def open_connection(port_url: str, model: str) -> serial.serialutil.SerialBase:

    ser = serial.serial_for_url(port_url, do_not_open=True)
    ser.baudrate = config[model]["comms"]["transport"]["baudrate"]
    ser.stopbits = config[model]["comms"]["transport"]["stopbits"]
    ser.bytesize = config[model]["comms"]["transport"]["bytesize"]
    ser.parity = config[model]["comms"]["transport"]["parity"]
    ser.timeout = config[model]["comms"]["transport"]["timeout"]
    ser.write_timeout = config[model]["comms"]["transport"]["write_timeout"]
    ser.open()
    return ser


lock = RLock()


def synchronized(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args, **kwargs):  # type: ignore
        with lock:
            return func(*args, **kwargs)

    return wrapper


async_lock = asyncio.Lock()


def locked(coro: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(coro)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        async with async_lock:
            return await coro(*args, **kwargs)

    return wrapper


class SyncRequest:
    def __init__(self, port_url: str, model: str, retries: Optional[int] = None):
        self._port = open_connection(port_url, model)
        self.model = model
        if retries:
            self._retries = retries
        else:
            self._retries = REQUEST_RETRIES

    def __call__(self, *args: Any) -> Any:
        return self._retry_request(*args)

    @synchronized
    def _retry_request(
        self, request: str, request_string: str, response_cls: Any,
    ) -> Any:

        # rtn: Optional[NuvoClasses] = None
        rtn = None
        excp = None

        for count in range(1, self._retries + 2):
            try:
                data_obj = response_cls.from_string(self._process_request(request))
                if data_obj:
                    rtn = data_obj
                    break
                else:
                    _LOGGER.debug(
                        "%s Request - Response Invalid - Retry Count: %d",
                        request_string,
                        count,
                    )
            except Exception as e:
                if count == self._retries + 1:
                    raise

                excp = e
                excp_str = repr(excp)
                _LOGGER.debug("Request: %s raised %s", request_string, excp_str)
                rtn = None

            time.sleep(REQUEST_RETRY_DELAY)

        if not rtn:
            raise ValueError(
                f'{request_string} using request "{request}" - Response Invalid'
            )

        return rtn

    def _send_request(self, request: str) -> None:
        """
        :param request: request that is sent to the nuvo
        :return: bool if transmit success
        """
        # format and send output command
        lineout = "*" + request + "\r"
        _LOGGER.debug('Sending "%s"', request)
        self._port.write(lineout.encode("ascii"))
        self._port.flush()  # it is buffering

    def _listen_maybewait(self, wait_for_response: bool) -> Optional[str]:

        message = b""
        start_time = time.time()
        timeout = TIMEOUT_RESPONSE
        reply = None

        # listen for response
        while True:

            # Exit if timeout
            if (time.time() - start_time) > timeout:
                _LOGGER.warning(
                    "Expected response from command but no response before timeout"
                )
                break

            data = self._port.readline()

            if data:
                _LOGGER.debug("CONTENTS OF DATA %s", data)
                message, sep, data = data.partition(
                    config[self.model]["comms"]["protocol"]["eol"]
                )
                _LOGGER.debug("Received: %s", message)
                reply = message.decode("ascii")
                break

            else:
                _LOGGER.debug("Expecting response from command sent - No Data received")
                if not wait_for_response:
                    # no_data = False
                    break

        return reply

    def _process_request(self, request: str) -> Optional[str]:
        """
        :param request: request that is sent to the nuvo
        :return: ascii response_string returned by nuvo
        """

        # Process any messages that have already been received
        self._listen_maybewait(False)

        # Send command to device
        self._send_request(request)

        # Process expected response
        return self._listen_maybewait(True)


class MsgBus:
    def __init__(self) -> None:
        self.subscribers: dict[str, set[Callable[..., Coroutine]]] = {}

    def add_subscriber(
        self, subscriber: Callable[..., Coroutine], event_name: str
    ) -> None:
        if not self.subscribers.get(event_name, None):
            self.subscribers[event_name] = {subscriber}
        else:
            self.subscribers[event_name].add(subscriber)

    def remove_subscriber(
        self, subscriber: Callable[..., Coroutine], event_name: str
    ) -> None:
        self.subscribers[event_name].remove(subscriber)
        if len(self.subscribers[event_name]) == 0:
            del self.subscribers[event_name]

    # def emit_event(self, event_name: NuvoMsgType, event: NuvoClass) -> None:
    def emit_event(self, event_name: str, event: NuvoClass) -> None:
        message = {"event_name": event_name, "event": event}
        for subscriber in self.subscribers.get(event_name, set()):
            asyncio.create_task(subscriber(message))


class AsyncConnection:
    def __init__(
        self,
        port_url: str,
        model: str,
        bus: MsgBus,
        timeout: Optional[float] = TIMEOUT_RESPONSE,
        disconnect_time: Optional[float] = DISCONNECT_TIME,
    ):
        self._port_url = port_url
        self._model = model
        self._reader: asyncio.StreamReader
        self._writer: asyncio.StreamWriter
        self._bus = bus

        if timeout:
            self._timeout = timeout
        else:
            self._timeout = TIMEOUT_RESPONSE

        if disconnect_time:
            self._disconnect_time = disconnect_time
        else:
            self._disconnect_time = DISCONNECT_TIME

        self._connected: bool = False
        self._f_connected: asyncio.futures.Future[Any]
        self._streaming_task = asyncio.get_running_loop().create_future()
        self._streaming_task.set_result(True)
        self._eol = config[self._model]["comms"]["protocol"]["eol"]
        self._eol_pattern = re.compile(b"(?P<message>.+?" + self._eol + b")")

    async def connect(self) -> None:
        """
        StreamReader/StreamWriter method
        """
        serial_settings = config[self._model]["comms"]["transport"]
        self._reader, self._writer = await serial_asyncio.open_serial_connection(
            url=self._port_url, **serial_settings
        )
        self._connected = True
        self._start_streaming_reader()

    async def disconnect(self, stop_streaming_reader: bool = True) -> None:
        self._connected = False
        if stop_streaming_reader:
            await self._stop_streaming_reader()
        self._writer.close()
        await self._writer.wait_closed()
        # Some serial ports/slower machines need a pause here if a quick reconnect
        # will take place
        await asyncio.sleep(self._disconnect_time)

    async def _reconnect(self) -> None:
        """Attempt reconnection to the Nuvo.
        Don't try to self.disconnect() first, it will often hang if there's been a
        problem with the serial port
        """

        _LOGGER.info("RECONNECT: Attempting reconnection")

        self._connected = False
        self._f_connected = asyncio.get_running_loop().create_future()

        while not self._connected:
            try:
                await self.connect()
            except SerialException as exc:
                _LOGGER.error(
                    "RECONNECT: received SerialException when attempting a connection: %s",
                    exc,
                )
                await asyncio.sleep(1)
            else:
                _LOGGER.info("RECONNECT: connection successful")
                self._connected = True
                self._f_connected.set_result("connected")

    async def send_message_without_reply(self, message: str) -> None:
        await self._send(format_message(self._model, message))

    # @overload
    # async def send_message(self, msg: str, message_types: Literal[ZONE_STATUS]) -> ZoneStatus: ...

    # @overload
    # async def send_message(
    #     self,
    #     msg: str,
    #     message_types: Tuple[Literal["ZoneButton"], Literal["ZoneStatus"]],
    # ) -> ZoneButton:
    #     ...

    @overload
    async def send_message(
        self,
        msg: str,
        message_types: Literal["ZoneAllOff"],
    ) -> ZoneAllOff:
        ...

    @overload
    async def send_message(
        self,
        msg: str,
        message_types: Tuple[Literal["ZoneButton"], Literal["ZoneStatus"]],
    ) -> ZoneButton:
        ...

    @overload
    async def send_message(
        self, msg: str, message_types: Literal["ZoneEQStatus"]
    ) -> ZoneEQStatus:
        ...

    @overload
    async def send_message(
        self, msg: str, message_types: Literal["ZoneStatus"]
    ) -> ZoneStatus:
        ...

    @overload
    async def send_message(
        self, msg: str, message_types: Literal["ZoneVolumeConfiguration"]
    ) -> ZoneVolumeConfiguration:
        ...

    @overload
    async def send_message(
        self, msg: str, message_types: Literal["ZoneConfiguration"]
    ) -> ZoneConfiguration:
        ...

    @overload
    async def send_message(
        self, msg: str, message_types: Literal["SourceConfiguration"]
    ) -> SourceConfiguration:
        ...

    @overload
    async def send_message(
        self, msg: str, message_types: Literal["Version"]
    ) -> Version:
        ...

        # self, msg: str, message_types: Union[NuvoMsgType, Tuple[NuvoMsgType, ...]]

    async def send_message(
        self, msg: str, message_types: Union[NuvoMsgType, Tuple[NuvoMsgType, ...]]
    ) -> NuvoClass:
        """Send a message to the Nuvo and wait for a response."""

        self._message = msg  # For pytest to access the message

        if not isinstance(message_types, tuple):
            message_types = (message_types,)

        if not self._connected:
            _LOGGER.warning(
                "RESPONSEREADER: Cannot proceed due to disconnection, awaiting reconnection..."
            )
            await self._f_connected

        await self._stop_streaming_reader()
        message = format_message(self._model, msg)

        try:
            await self._send(message)
        except SerialException as exc:
            _LOGGER.error(
                "RESPONSEREADER Reconnecting due to SerialException when WRITING"
            )
            # Attempt reconnection
            self._reconnect_task = asyncio.create_task(
                self._reconnect(), name="ReconnectTask"
            )
            raise MessageResponseError(
                "RESPONSEREADER: Serial Port error when writing message: %s", exc
            )

            response: Tuple[str, NuvoClass]
            # response: Tuple[NuvoMsgType, NuvoClass]

        """Possible problems here:

            _message_response_reader should return the correct message type or?
            timeout
            message read from buffer is garbage format
            message read from buffer is correct nuvo message format:
                but cannot be classified
                classified but not wanted message_type
                classified and is the wanted message_type
        """
        try:
            _LOGGER.debug("RESPONSEREADER: Attempting to obtain response")
            response = await asyncio.wait_for(
                self._message_response_reader(message_types), self._timeout
            )
            _LOGGER.debug("RESPONSEREADER: Response: %s", repr(response))
        except TimeoutError as exc:
            err_msg = "RESPONSEREADER: Timeout waiting for response to message: {}".format(
                message.decode()
            )
            _LOGGER.debug("%s", err_msg)
            self._start_streaming_reader()
            raise MessageResponseError(err_msg) from exc
        except SerialException as exc:
            _LOGGER.error(
                "RESPONSEREADER Reconnecting due to SerialException when READING"
            )
            # Attempt reconnection
            self._reconnect_task = asyncio.create_task(
                self._reconnect(), name="ReconnectTask"
            )
            raise MessageResponseError(
                "RESPONSEREADER: Serial Port error when reading message response: %s",
                exc,
            )
        else:
            self._start_streaming_reader()
            self._bus.emit_event(response[0], response[1])
            return response[1]

    async def _send(self, message: bytes) -> None:
        _LOGGER.debug("SENDINGMESSAGE: {!r}".format(message))
        self._writer.write(message)

    def _streaming_task_done_cb(self, *args: Any, **kwargs: Any) -> None:
        """Callback for the _streaming_reader task.

        When things are working correctly this callback should never run, if it has,
        it means something has gone wrong.

        Task has either:
            Been cancelled
            Raised an exception
            Returned a value
        """

        try:
            self._streaming_task.result()
        except asyncio.CancelledError:
            """Shouldn't get here during normal operation as _stop_streaming_task
            handles CancelledErrors and removes this callback, but can get here
            if the app using this lib doesn't cleanly disconnect e.g from ctrl-c
            but no need to report the error in that case. Any other exceptions raised in
            the task will be unhandled here and raised.
            """
            pass
        except SerialException:
            """
            There's a serious problem reading from the serial port read buffer.  
            Often happens if there's been two processes trying to use the serial port
            at the same time and StreamReader gets into an unrecoverable state.

            """

            _LOGGER.error("STREAMINGREADER task has ended prematurely due to exception")
            _LOGGER.error("STREAMINGREADER Reconnecting due to SerialException")
            # Attempt reconnection
            self._reconnect_task = asyncio.create_task(
                self._reconnect(), name="ReconnectTask"
            )
        except Exception:
            _LOGGER.error("STREAMINGREADER task has ended prematurely due to exception")
            raise

    def _start_streaming_reader(self) -> None:
        """Start the Streaming reader

        Starts a daemon task to monitor the Stream for nuvo messages, classifying
        and emitting the message to any registered listeners.
        """

        _LOGGER.debug("STREAMINGREADER: Starting")
        if self._streaming_task.done():
            self._streaming_task = asyncio.create_task(
                self._streaming_reader(), name="StreamingReader"
            )
            self._streaming_task.add_done_callback(self._streaming_task_done_cb)
        else:
            _LOGGER.warning(
                "STREAMINGREADER: Attempted to start an already running Streaming Reader"
            )

    async def _stop_streaming_reader(self) -> None:
        """Stop the Streaming reader"""

        _LOGGER.debug("STREAMINGREADER: Stopping")
        if not self._streaming_task.done():
            self._streaming_task.remove_done_callback(self._streaming_task_done_cb)
            self._streaming_task.cancel()
            try:
                await self._streaming_task
            except asyncio.CancelledError:
                # task is now cancelled
                _LOGGER.debug(
                    "STREAMINGREADER: Streaming Reader task cancelled status: %s",
                    self._streaming_task.cancelled(),
                )
        else:
            _LOGGER.warning(
                "STREAMINGREADER: Attempted to stop an already stopped Streaming Reader"
            )

    async def _streaming_reader(self) -> None:
        """Monitor the Stream for known nuvo messages. 
        Classifies and emits the message to any registered listeners.
        Designed to run as a background task when there is no command waiting for a 
        response and will receive messages sent by the Nuvo in response to Zone keypad 
        inputs. 
        Run this as a Task that can be stopped with task.cancel()
        """
        while True:
            try:
                message = await self._read_message_from_buffer()
                processed_type, data = process_message(self._model, message)
                if processed_type:
                    self._bus.emit_event(processed_type, data)
            except asyncio.CancelledError:
                _LOGGER.debug("STREAMINGREADER: Task was cancelled")
                """
                Always rereaise the CancelledError so the canceller can check the status
                """
                raise
            except SerialException as exc:
                _LOGGER.debug("STREAMINGREADER: SerialException: %s", exc)
                # await asyncio.sleep(1)
                raise
            except MessageFormatError as exc:
                _LOGGER.debug(
                    "STREAMINGREADER: Garbled message found in stream, possible multiple access on serial port: %s",
                    exc,
                )
            except MessageClassificationError as exc:
                # There may well be propely formatted messages that cannot be classified yet as
                # a handler hasn't been implemented, this is not an anomalous condition
                _LOGGER.debug(
                    "STREAMINGREADER: MessageClassificationError: %s", repr(exc)
                )

    # async def _message_response_reader(self, message_types: Tuple[NuvoMsgType, ...]) -> Tuple[str, NuvoClass]:
    async def _message_response_reader(
        self, message_types: Tuple[str, ...]
    ) -> Tuple[str, NuvoClass]:
        """
        Return a dataclass of message_type.
        This needs to be ran as a task with a timeout.
        """

        match: Tuple[str, NuvoClass]
        # match: Tuple[NuvoMsgType, NuvoClass]
        found_match = False

        while not found_match:
            try:
                message = await self._read_message_from_buffer()
            except asyncio.CancelledError:
                _LOGGER.debug(
                    "RESPONSEREADER: CancelledError inner task cancel request caught"
                )
                """
                Always reraise the CancelledError so the canceller can check the status
                """
                raise
            except SerialException as exc:
                _LOGGER.debug("RESPONSEREADER: SerialException: %s", exc)
                # await asyncio.sleep(1)
                raise
            except MessageFormatError as exc:
                _LOGGER.warning(
                    "RESPONSEREADER: Garbled message found in stream, possible multiple access on serial port: %s",
                    exc,
                )
            except Exception as exc:
                _LOGGER.exception(
                    "RESPONSEREADER: Unknown Exception raised from buffer read"
                )
                await asyncio.sleep(1)
            else:
                # A message with the correct Nuvo message format was retrieved from the
                # stream, now process it looking for the message_type
                try:
                    processed_type, d_class = process_message(self._model, message)
                except MessageClassificationError as exc:
                    # There may well be propely formatted messages that cannot be classified yet as
                    # a handler hasn't been implemented, this is not an anomalous condition
                    _LOGGER.debug("RESPONSEREADER: MessageClassificationError: %s", exc)
                else:
                    # There message has been classified but it may not be the wanted
                    # message_type
                    # if processed_type == message_type:
                    if processed_type in message_types:
                        _LOGGER.debug(
                            "RESPONSEREADER: Found matching response: %s", d_class
                        )
                        found_match = True
                        match = (processed_type, d_class)
                        break
                    else:
                        # The message has been classified but it's not the wanted
                        # message_type
                        _LOGGER.debug(
                            "RESPONSEREADER: Mismatch Wanted %s but got %s %s reponse",
                            repr(message_types),
                            processed_type,
                            d_class,
                        )
                        self._bus.emit_event(processed_type, d_class)
        return match

    async def _read_message_from_buffer(self) -> bytes:
        """Get a message from the read buffer.
        This can raise many Exceptions which must be handled in the caller.
        """
        message = await self._reader.readuntil(self._eol)
        # We have bytes with the correct eol chars but is it in the correct format?
        if re.match(b"#.+?" + self._eol, message):
            return message
        else:
            raise MessageFormatError(message)
