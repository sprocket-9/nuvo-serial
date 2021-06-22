# nuvo-serial
Python API implementing the Nuvo Grand Concerto/Essentia G multi-zone audio amplifier serial control protocol.


## Notes
A [Nuvo Integration](https://github.com/sprocket-9/hacs-nuvo-serial) built using this library, is available to control a Nuvo through a [Home Assistant](https://www.home-assistant.io/) frontend.

## Usage

Supported models: "Grand_Concerto" and "Essentia_G"

async and sync version of most commands.

Commands return instances of a python dataclass which represents the Nuvo response message type:

```
* ZoneStatus
* ZoneConfiguration
* ZoneVolumeConfiguration
* ZoneEQStatus
* ZoneButton
* ZoneAllOff
* SourceConfiguration
* Version
```
## Connection
Direct serial cable or remote network connection using hardware serial-to-network adapter or software such as [ser2net](https://linux.die.net/man/8/ser2net) will
work, all that is needed is a change of the port_url argument:

E.g:

Local: ```/dev/ttyUSB1```

Remote: ```socket://host:port```

A possible ser2net configuration connecting TCP port 10003 to the nuvo device on /dev/ttyUSB1:

```10003:raw:0:/dev/ttyUSB1:57600 8DATABITS NONE 1STOPBIT```

 ```port_url="socket://192.168.5.1:10003"```

## Synchronous Interface

Not all the available setter methods are
shown, but there are methods to configure most fields in each of the data classes.

```python
from nuvo_serial import get_nuvo

nuvo = get_nuvo(port_url='/dev/ttyUSB0', model='Grand_Concerto')

print(nuvo.get_version()
# Version(model='Grand_Concerto', product_number='NV-I8G', firmware_version='FWv2.66', hardware_version='HWv0')

print(nuvo.zone_status(1))
# ZoneStatus(zone=1, power=True, source=1, volume=20, mute=False, dnd=False, lock=False)

print(nuvo.zone_configuration(1))
# ZoneConfiguration(zone=1, enabled=True, name='Music Room', slave_to=0, group=0, sources=['SOURCE1'], exclusive_source=False, ir_enabled=1, dnd=[], locked=False, slave_eq=0)

print(nuvo.zone_volume_configuration(1))
# ZoneVolumeConfiguration(zone=1, max_vol=33, ini_vol=20, page_vol=40, party_vol=50, vol_rst=False)

print(nuvo.zone_eq_status(1))
# ZoneEQStatus(zone=1, bass=-2, treble=0, loudcmp=True, balance_position='C', balance_value=0)

print(nuvo.source_configuration(2))
# SourceConfiguration(source=2, enabled=True, name='Sonos', gain=4, nuvonet_source=False, short_name='SON')

# Turn off zone #1
print(nuvo.set_power(1, False))
# ZoneStatus(zone=1, power=False, source=None, volume=None, mute=None, dnd=None, lock=None)

# Mute zone #1
nuvo.set_mute(1, True)
# ZoneStatus(zone=1, power=True, source=1, volume=None, mute=True, dnd=False, lock=False)

# Change Zone name
print(nuvo.zone_set_name(1, "Kitchen"))
# ZoneConfiguration(zone=1, enabled=True, name='Kitchen', slave_to=0, group=0, sources=['SOURCE1'], exclusive_source=False, ir_enabled=1, dnd=[], locked=False, slave_eq=0)

# Change Zone's permitted sources
print(nuvo.zone_set_source_mask(1, ['SOURCE3', 'SOURCE4']))
ZoneConfiguration(zone=1, enabled=True, name='Kitchen', slave_to=0, group=0, sources=['SOURCE3', 'SOURCE4'], exclusive_source=False, ir_enabled=1, dnd=[], locked=False, slave_eq=0)

# Change Zone max volume
print(nuvo.zone_volume_max(1, 20))
# ZoneVolumeConfiguration(zone=1, max_vol=20, ini_vol=20, page_vol=40, party_vol=50, vol_rst=False)

# Change Zone Bass
print(nuvo.set_bass(1, 6))
# ZoneEQStatus(zone=1, bass=6, treble=0, loudcmp=True, balance_position='C', balance_value=0)

# Set volume for zone #1
nuvo.set_volume(1, 15)

# Set source 2 for zone #1 
nuvo.set_source(1, 2)

# Set balance for zone #1
nuvo.set_balance(1, L, 8)
# ZoneEQStatus(zone=1, bass=-2, treble=0, loudcmp=True, balance_position='L', balance_value=8)

```

## Asynchronous Interface

All the method names and syntax are as above in the sync interface, but now all the methods are coroutines and must
be awaited.

An added feature with the async interface is it will constantly monitor the
serial line and attempt to classify any messages emitted by the Nuvo.
A subscriber to these messages in the form of a coroutine callback can optionally be added
for any of the Nuvo message data classes.  This allows receiving messages sent
by the Nuvo in response to commands initiated from Zone keypads.

```python

import asyncio
from nuvo_serial import get_nuvo_async

async def message_receiver(message: dict):
    print(message)
    # e.g. {'event_name': 'ZoneStatus', 'event': ZoneStatus(zone=1, power=True, source=1, volume=None, mute=True, dnd=False, lock=False)}
    # e.g. {'event_name': 'ZoneButton', 'event': ZoneButton(zone=1, source=1, button='PLAYPAUSE')}

async def main():

    nuvo = await get_nuvo_async('/dev/ttyUSB0', 'Grand_Concerto')

    print(await nuvo.zone_status(1))
    # ZoneStatus(zone=1, power=True, source=1, volume=20, mute=False, dnd=False, lock=False)
   
    """message_receiver coro will be called everytime a ZoneStatus message is received
    from the Nuvo."""
   nuvo.add_subscriber(message_receiver, "ZoneStatus")

   nuvo.add_subscriber(message_receiver, "ZoneButton")
   ...
   nuvo.remove_subscriber(message_receiver, "ZoneStatus")
   nuvo.disconnect()


loop = asyncio.get_event_loop()
loop.run_until_complete(main())

```
