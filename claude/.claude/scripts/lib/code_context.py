"""code_context.py: the warning a /code prompt gets when the main session already holds a large context. A /code run
re-reads the main context on every reply, so a run that starts above the limit reads about twice the cache of one
that starts small. Not a hook itself: format_changed.py calls it on UserPromptSubmit, so no new process starts."""
import json
import re
import sys

import script_utils

# Claude Code's own notices (usage limit, "No response requested") are assistant records with every count at 0.
SYNTHETIC_MODEL = "<synthetic>"
CONTEXT_LIMIT = 100_000
# Bytes read back from the end of the transcript to find the last main reply: replies carry their usage, and the
# newest one sits near the end.
TAIL_BYTES = 1 << 20
# A typed /code run start: `/code` alone or followed by its arguments, but not `/code resume`, which goes on with a
# run already started, and not another skill whose name starts with code.
CODE_START = re.compile(r"/code(?:\s|$)(?!\s*resume\b)")
USAGE_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def is_code_start(prompt):
    return CODE_START.match(prompt.lstrip()) is not None


def reply_tokens(record):
    """The context a main-session reply was sent with (fresh input, cache write and cache read), or None for any
    other record."""
    if record.get("type") != "assistant" or record.get("isSidechain"):
        return None
    message = record.get("message") or {}
    if message.get("model") == SYNTHETIC_MODEL:
        return None
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return None
    counts = [usage.get(key) for key in USAGE_KEYS]
    if not any(isinstance(count, int) for count in counts):
        return None
    return sum(count for count in counts if isinstance(count, int))


def context_tokens(transcript_path):
    """The context of the newest main-session reply in the transcript, or None when there is none or it cannot be
    read."""
    # Fails open: a transcript that cannot be read gives no warning, so /code is never held up.
    try:
        tail_lines = script_utils.transcript_tail_lines(transcript_path, TAIL_BYTES)
    except FileNotFoundError:
        return None  # a new session has no transcript yet
    except OSError as error:
        print(f"format_changed/code_context: could not read {transcript_path}, {type(error).__name__}: {error}",
              file=sys.stderr)
        return None
    for line in reversed(tail_lines):
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        if record.get("type") == "system" and record.get("subtype") == "compact_boundary":
            return None  # /compact wrote no reply after this yet; the replies before it are the old context
        tokens = reply_tokens(record)
        if tokens is not None:
            return tokens
    return None


def code_start_warning(prompt, transcript_path):
    """The systemMessage line for a /code start over the limit, or None."""
    if not is_code_start(prompt):
        return None
    tokens = context_tokens(transcript_path)
    if tokens is None or tokens <= CONTEXT_LIMIT:
        return None
    message = (f"Main session context is {tokens // 1000}k tokens as /code starts, over {CONTEXT_LIMIT // 1000}k. "
               "A run this large reads about twice the cache of a small one. Run /clear, then /code again.")
    return json.dumps({"systemMessage": message}) + "\n"
