from __future__ import annotations

from copy import deepcopy
from typing import Any, Final, Literal, Union

from nuvo_serial.const import MODEL_GC, MODEL_ESSENTIA_G

TIMEOUT_OP = 0.2  # Number of seconds before serial operation timeout

config: dict[str, Any] = {}
config[MODEL_GC] = {
    "zones": {
        "physical": 16,
        "logical": 4,
        "logical_start_zone": 17,
        "total": 20,
        "name_max_length": 20,
        "slave_to": {"max": 16, "min": 0, "step": 1},
        "group": {"max": 4, "min": 0, "step": 1},
        "ir": {"max": 2, "min": 0, "step": 1},
    },
    "sources": {"total": 6, "name_long_max_length": 20, "name_short_max_length": 3},
    "volume": {"max": 0, "min": 79, "step": 1},
    "bass": {"max": 18, "min": -18, "step": 2},
    "treble": {"max": 18, "min": -18, "step": 2},
    "balance": {"max": 18, "min": 0, "step": 2, "positions": ("L", "C", "R")},
    "gain": {"max": 14, "min": 0, "step": 1},
    "comms": {
        "transport": {
            "baudrate": 57600,
            "stopbits": 1,
            "bytesize": 8,
            "parity": 'N',
            "timeout": TIMEOUT_OP,
            "write_timeout": TIMEOUT_OP,
        },
        "protocol": {"eol": b"\r\n", "error_response": b"#?\r\n"}
    }
}


config[MODEL_ESSENTIA_G] = deepcopy(config[MODEL_GC])
config[MODEL_ESSENTIA_G]["zones"]["physical"] = 12
config[MODEL_ESSENTIA_G]["zones"]["logical"] = 6
config[MODEL_ESSENTIA_G]["zones"]["logical_start_zone"] = 15
config[MODEL_ESSENTIA_G]["zones"]["total"] = 18

