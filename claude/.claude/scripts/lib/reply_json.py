"""Reads a JSON value out of a model reply that may not be valid JSON as a whole."""

import json
import re


def list_after_last_key(reply, key_pattern):
    """(found, value, key_start) for the JSON value after the last match of `key_pattern` in a reply. `key_pattern`
    must end where the list begins (consume trailing whitespace and anchor on `(?=\\[)`): the decode starts at the
    match end and does not skip whitespace. `found` is False when the key is absent; `value` is None when the key is
    present and its list does not decode."""
    keys = list(key_pattern.finditer(reply))
    if not keys:
        return False, None, -1

    last_key = keys[-1]
    try:
        value, _ = json.JSONDecoder().raw_decode(reply, last_key.end())
    except json.JSONDecodeError:
        return True, None, last_key.start()
    return True, value, last_key.start()


def last_json_object(reply, keys):
    """The last JSON object in a reply that holds any of `keys`, or None. Decodes from each "{" back to front, because
    prose before the object can hold braces of its own ("{CUBE}")."""
    decoder = json.JSONDecoder()
    brace_positions = [match.start() for match in re.finditer(r"\{", reply)]
    for position in reversed(brace_positions):
        try:
            parsed, _ = decoder.raw_decode(reply, position)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and any(key in parsed for key in keys):
            return parsed
    return None
