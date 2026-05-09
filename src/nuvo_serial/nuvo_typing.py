from typing import Literal, Union

NuvoMsgType = Union[
    Literal["AllOff"],
    Literal["OKResponse"],
    Literal["Mute"],
    Literal["Paging"],
    Literal["Party"],
    Literal["SourceConfiguration"],
    Literal["Version"],
    Literal["ZoneAllOff"],
    Literal["ZoneButton"],
    Literal["ZoneConfiguration"],
    Literal["ZoneEQStatus"],
    Literal["ZoneStatus"],
    Literal["ZoneVolumeConfiguration"]
]
