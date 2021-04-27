import re
from tests.command_response import command_patterns, responses


def find_response(msg, model):
    """Return a Response string corresponding the to the msg"""

    found_match = None

    for command, pattern in command_patterns[model].items():
        if re.match(pattern, msg):
            found_match = responses[model][command]
            break

    if not found_match:
        raise Exception(f"TEST_SUITE_PROBLEM - No regex found matching message request {msg}")

    return found_match
