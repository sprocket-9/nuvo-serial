from typing import Literal, Union

NuvoMsgType = Union[
    Literal["SourceConfiguration"],
    Literal["Version"],
    Literal["SourceConfiguration"],
    Literal["ZoneButton"],
    Literal["ZoneConfiguration"],
    Literal["ZoneEQStatus"],
    Literal["ZoneStatus"],
    Literal["ZoneVolumeConfiguration"]
]
