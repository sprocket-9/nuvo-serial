from typing import Final

MODEL_GC: Final = "Grand_Concerto"
MODEL_ESSENTIA_G: Final = "Essentia_G"

ERROR_RESPONSE: Final = "ErrorResponse"
OK_RESPONSE: Final = "OKResponse"
SOURCE_CONFIGURATION: Final = "SourceConfiguration"
SYSTEM_VERSION: Final = "Version"
SYSTEM_MUTE: Final = "Mute"
SYSTEM_PAGING: Final = "Paging"
SYSTEM_PARTY: Final = "Party"
SYSTEM_RESTART: Final = "Restart"
ZONE_STATUS: Final = "ZoneStatus"
ZONE_CONFIGURATION: Final = "ZoneConfiguration"
ZONE_VOLUME_CONFIGURATION: Final = "ZoneVolumeConfiguration"
ZONE_EQ_STATUS: Final = "ZoneEQStatus"
ZONE_BUTTON: Final = "ZoneButton"
ZONE_ALL_OFF: Final = "ZoneAllOff"


ZONE_BUTTON_PLAY_PAUSE: Final = "PLAYPAUSE"
ZONE_BUTTON_PREV: Final = "PREV"
ZONE_BUTTON_NEXT: Final = "NEXT"

ZONE_BUTTON_TRANSFORM = {
    ZONE_BUTTON_PLAY_PAUSE: "keypad_play_pause",
    ZONE_BUTTON_PREV: "keypad_prev",
    ZONE_BUTTON_NEXT: "keypad_next",
}

RESPONSE_STRING_OK = "#OK"
RESPONSE_STRING_ERROR = "#?"

EMIT_LEVEL_ALL = "emit_all"
EMIT_LEVEL_EXTERNAL = "emit_external"
EMIT_LEVEL_INTERNAL = "emit_internal"
EMIT_LEVEL_NONE = "emit_none"

WAKEUP_PAUSE_SECS: Final = 0.005
