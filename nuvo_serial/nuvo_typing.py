from typing import Literal, Union

NuvoMsgType = Union[
    Literal["AllOff"],
    Literal["OKResponse"],
    Literal["SourceConfiguration"],
    Literal["Version"],
    Literal["ZoneButton"],
    Literal["ZoneConfiguration"],
    Literal["ZoneEQStatus"],
    Literal["ZoneStatus"],
    Literal["ZoneVolumeConfiguration"]
]
