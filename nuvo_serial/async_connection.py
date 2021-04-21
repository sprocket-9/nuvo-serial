from __future__ import annotations

import asyncio
import serial_asyncio
from nuvo_serial import get_nuvo_async
import logging

# _LOGGER = logging.getLogger('root')
# _LOGGER = logging.getLogger(__name__)
_LOGGER = logging.getLogger('nuvo_serial')
logging.basicConfig(level=logging.DEBUG)
# logging.basicConfig()
_LOGGER.setLevel(logging.DEBUG)
logging.getLogger('asyncio').setLevel(logging.DEBUG)
# _LOGGER.debug(_LOGGER.name)

# class EventBus:

#     def __init__(self):
#         self.listeners = {}

#     def add_listener(self, event_name, listener):
#         if not self.listeners.get(event_name, None):
#             self.listeners[event_name] = {listener}
#         else:
#             self.listeners[event_name].add(listener)

#     def remove_listener(self, event_name, listener):
#         self.listeners[event_name].remove(listener)
#         if len(self.listeners[event_name]) == 0:
#             del self.listeners[event_name]

#     def emit(self, event_name, event):
#         listeners = self.listeners.get(event_name, [])
#         for listener in listeners:
#             asyncio.create_task(listener(event))


# class MessageProcessor:
#     def process(self, message):
#         print(f"process message: {message}")
#         """
#         Match mesage against message patterns
#         Instantiate dataclass
#         Notify subcribers, passing dataclass
#         """


# class Output(asyncio.Protocol):
#     def __init__(self):
#         self._message_received = b""
#         self.processor = MessageProcessor()

#     def connection_made(self, transport):
#         self.transport = transport
#         print("port opened", transport)
#         transport.serial.rts = False  # You can manipulate Serial object via transport
#         transport.write(b"Hello, World!\n")  # Write serial data via transport

#     def data_received(self, data):
#         print("data received", repr(data))
#         self._message_received += data
#         print(f"message: {self._message_received}")
#         if b"\n" in data:
#             self.processor.process(self._message_received)
#             self._message_received = b""

#         #     self.transport.close()

#     def connection_lost(self, exc):
#         print("port closed")
#         self.transport.loop.stop()

#     def pause_writing(self):
#         print("pause writing")
#         print(self.transport.get_write_buffer_size())

#     def resume_writing(self):
#         print(self.transport.get_write_buffer_size())
#         print("resume writing")

#     def write_data(self, request):
#         print("in write_data")
#         # self.transport.write(self.message)
#         self.transport.write(self.format_request(request))

#     def format_request(self, request):
#         lineout = "*" + request + "\r"
#         # _LOGGER.debug('Sending "%s"', request)
#         return lineout.encode("ascii")
#         # self._port.write(lineout.encode("ascii"))
#         # self._port.flush()  # it is buffering


# async def create_serial_connection(port: str, loop=None, **kwargs):
#     if not loop:
#         loop = asyncio.get_event_loop()
#     # coro = serial_asyncio.create_serial_connection(
#     #     loop, Output, "/dev/ttyUSB0", baudrate=57600
#     # )
#     # return coro
#     return await serial_asyncio.create_serial_connection(
#         loop, Output, port, baudrate=57600
#     )

# def _create_serial_connection(loop=None):
#     if not loop:
#         loop = asyncio.get_event_loop()
#     coro = serial_asyncio.create_serial_connection(
#         loop, Output, "/dev/ttyUSB0", baudrate=57600
#     )
#     return coro


# async def main():
#     print("in main")
#     coro = create_serial_connection()
#     transport, protocol = await asyncio.create_task(coro)
#     # import pdb; pdb.set_trace()
#     print("in main2")
#     protocol.write_data("Z1STATUS?")

# port = '/dev/ttyUSB0gfgfgfg'
port = '/dev/ttyUSB0'
model = 'Grand_Concerto'


def set_zone_power(nuvo, zone, power):
    task = asyncio.get_running_loop().create_task(nuvo.set_power(zone, power))


def set_zones_power(nuvo, power):
    for zone in range(1, 2):
        set_zone_power(nuvo, zone, power)


def get_zone_status(nuvo, zone):
    task = asyncio.get_running_loop().create_task(nuvo.zone_status(zone))


def get_zone_states(nuvo):
    for zone in range(1, 9):
        get_zone_status(nuvo, zone)

async def _update_callback(event):
    _LOGGER.debug(event)


async def main():
    loop = asyncio.get_running_loop()
    _LOGGER.debug("in main")
    nuvo = await get_nuvo_async(port, model)
    _LOGGER.debug("got nuvo object")
    nuvo.add_subscriber(_update_callback, "ZoneStatus")
    await nuvo.zone_configuration(1)
    # await nuvo.set_power(1, True)
    button = await nuvo.zone_button_play_pause(6)
    print(button)
    await nuvo.set_power(2, True)
    all_off = await nuvo.all_off()
    # button = await nuvo.zone_button_prev(1)
    # print(button)
    # button = await nuvo.zone_button_next(1)
    # print(button)
    # nuvo.zone_status(1)
    # loop.call_later(3, get_zone_status, nuvo, 1)
    # loop.call_later(1, get_zone_states, nuvo)
    # set_zones_power(nuvo, True)
    # coro = create_serial_connection()
    # transport, protocol = await asyncio.create_task(coro)
    # # import pdb; pdb.set_trace()
    # print("in main2")
    # protocol.write_data("Z1STATUS?")

loop = asyncio.get_event_loop()
# coro = serial_asyncio.create_serial_connection(loop, Output, '/dev/ttyUSB0', baudrate=57600)
# loop.run_until_complete(coro)
loop.run_until_complete(main())
loop.run_forever()
loop.close()
