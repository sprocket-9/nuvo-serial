import re
from tests.command_response import command_patterns, responses


def find_response(msg, model):
    """Return a Response string corresponding the to the msg"""

    found_match = None

    for command, pattern in command_patterns[model].items():
        if re.search(pattern, msg):
            found_match = responses[model][command]
            break

    if not found_match:
        raise Exception(f"Unhandled response for message request {msg}")

    return found_match
