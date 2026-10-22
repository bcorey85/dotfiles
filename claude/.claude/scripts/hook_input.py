"""Helpers shared by the Python hook ports. Python 3.9 stdlib only.

Each port does `import hook_input`; python3 puts the script's own directory first on sys.path, so this file must sit
beside the ports. Not a hook itself.
"""
import json
import os
import re
import sys

JQ_WHITESPACE = " \t\r\n"


class JqError(Exception):
    """A jq runtime error. `JqError(5)` carries an exit code; `JqError("message")` carries jq's message (exit 5)."""

    def __init__(self, detail=5):
        Exception.__init__(self, detail)
        self.detail = detail
        self.rc = detail if isinstance(detail, int) else 5


def hook_name():
    return os.path.splitext(os.path.basename(sys.argv[0] or "hook"))[0]


def encode_out(text, errors="surrogateescape"):
    """Bytes for stdout or stderr. File text read with surrogateescape round-trips; a lone JSON surrogate cannot."""
    try:
        return text.encode("utf-8", errors)
    except UnicodeEncodeError:
        return text.encode("utf-8", "replace")


def read_stdin_text():
    return sys.stdin.buffer.read().decode("utf-8", "replace")


def emit_stderr(text):
    sys.stderr.buffer.write(encode_out(text))
    sys.stderr.buffer.flush()


def decision_line(decision, reason):
    """The one-line PreToolUse permission decision JSON, as `jq -nc` prints it."""
    encoded = json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                                 "permissionDecisionReason": reason}},
                         ensure_ascii=False, separators=(",", ":"))
    return encoded.replace("\x7f", "\\u007f") + "\n"


def emit_decision(decision, reason):
    sys.stdout.buffer.write(decision_line(decision, reason).encode("utf-8", "replace"))
    sys.stdout.buffer.flush()


def report_open_failure(error, path):
    """One plain line for a log or file the hook could not open. The hook goes on without it."""
    text = "%s: cannot open %s: %s\n" % (hook_name(), path, os.strerror(error.errno or 0))
    emit_stderr(text)


def jq_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def truthy(value):
    return value is not None and value is not False


def present(value, default=""):
    """jq `// default`: null and false fall through."""
    return value if truthy(value) else default


def first_truthy(*thunks):
    """jq `a // b // c`: the first truthy value, evaluated lazily, else the last thunk's value."""
    for thunk in thunks[:-1]:
        value = thunk()
        if truthy(value):
            return value
    return thunks[-1]()


def index(value, key):
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(key)
    raise JqError('Cannot index %s with string ("%s")' % (jq_type(value), key))


def jq_get(obj, *keys):
    for key in keys:
        if obj is None:
            return None
        if not isinstance(obj, dict):
            raise JqError(5)
        obj = obj.get(key)
    return obj


def raw_text(value):
    """What `jq -r` prints for one value."""
    if isinstance(value, str):
        return value
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, (list, dict)):
        return json.dumps(value, indent=2, ensure_ascii=False)
    return json.dumps(value)


def jq_str(value):
    """What `jq -r '.x // ""'` prints, with the trailing newlines a shell $(...) drops."""
    if value is None or value is False:
        return ""
    return raw_text(value).rstrip("\n")


def parse_documents(text):
    """Every JSON document in the text, as jq reads them. Raises ValueError on a parse error."""
    decoder = json.JSONDecoder()
    documents = []
    position = 0
    length = len(text)
    while True:
        while position < length and text[position] in JQ_WHITESPACE:
            position += 1
        if position >= length:
            return documents
        document, position = decoder.raw_decode(text, position)
        documents.append(document)


def parse_documents_partial(text):
    """The documents that parse, then whether a parse error followed them (jq prints earlier outputs first)."""
    decoder = json.JSONDecoder()
    documents = []
    position = 0
    length = len(text)
    while True:
        while position < length and text[position] in JQ_WHITESPACE:
            position += 1
        if position >= length:
            return documents, False
        try:
            document, position = decoder.raw_decode(text, position)
        except ValueError:
            return documents, True
        documents.append(document)


def exit_code_in_error_text(text):
    """The N of a leading "Exit code N" line in a failed Bash tool's error text, as an int, or None when the text
    does not start with one."""
    found = re.match(r"Exit code (\d+)", text)
    return int(found.group(1)) if found else None


def bash_basename(path):
    stripped = path.rstrip("/")
    if stripped == "":
        return "/" if path else ""
    return stripped.rsplit("/", 1)[-1]


def bash_dirname(path):
    stripped = path.rstrip("/")
    if not stripped:
        return "/" if path else "."
    if "/" not in stripped:
        return "."
    head = stripped.rsplit("/", 1)[0].rstrip("/")
    return head or "/"


def current_directory():
    """`$PWD` as bash sees it: the inherited value when it still names the current directory."""
    inherited = os.environ.get("PWD", "")
    try:
        if inherited and os.path.isabs(inherited) and os.path.samefile(inherited, "."):
            return inherited
    except OSError:
        pass
    return os.getcwd()


def split_segments(command):
    """Split a shell command on ||, &&, | and ; into segments."""
    text = command.replace("||", "\n").replace("&&", "\n")
    return re.sub(r"[|;]", "\n", text).split("\n")


def _crc_table():
    table = []
    for byte in range(256):
        crc = byte << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04C11DB7) if crc & 0x80000000 else crc << 1
            crc &= 0xFFFFFFFF
        table.append(crc)
    return table


CRC_TABLE = _crc_table()


def cksum(data):
    """The POSIX cksum CRC of bytes, as `cksum` prints it."""
    crc = 0
    for byte in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ CRC_TABLE[((crc >> 24) ^ byte) & 0xFF]
    length = len(data)
    while length:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ CRC_TABLE[((crc >> 24) ^ length) & 0xFF]
        length >>= 8
    return (~crc) & 0xFFFFFFFF


def run_gate(main):
    """Run a gate's main() and exit with its code. A crash that escapes main blocks: one line naming the hook and
    the error goes to stderr and the exit code is 2, so the call does not run on a hook that died."""
    try:
        code = main()
    except SystemExit:
        raise
    except Exception as error:
        try:
            emit_stderr("%s: crashed (%s: %s) - blocking the call\n" % (hook_name(), type(error).__name__, error))
        except Exception:
            pass
        sys.exit(2)
    sys.exit(code or 0)
