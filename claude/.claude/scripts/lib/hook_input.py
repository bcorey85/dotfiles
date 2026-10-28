"""Helpers shared by the Python hook ports. Python 3.9 stdlib only.

Each port does `import hook_input` after putting scripts/lib on sys.path. Not a hook itself.
"""
import contextlib
import json
import os
import re
import sys
import tempfile
import time

JQ_WHITESPACE = " \t\r\n"
# The parsed payload of an empty stdin: jq prints nothing for it, so every field of it is empty.
EMPTY_INPUT = object()
STATE_MAX_AGE_DAYS = 2


class JqError(Exception):
    """A jq runtime error. `JqError(5)` carries an exit code; `JqError("message")` carries jq's message (exit 5)."""

    def __init__(self, detail=5):
        Exception.__init__(self, detail)
        self.detail = detail
        self.rc = detail if isinstance(detail, int) else 5


def hook_name():
    """The name stderr messages open with. Scripts are snake_case files; the name stays the kebab-case hook id."""
    script_stem = os.path.splitext(os.path.basename(sys.argv[0] or "hook"))[0]
    return script_stem.replace("_", "-")


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
    text = f"{hook_name()}: cannot open {path}: {os.strerror(error.errno or 0)}\n"
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
    raise JqError(f'Cannot index {jq_type(value)} with string ("{key}")')


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


def jq_output(documents, extract, error_line):
    """What `jq -r <extract>` leaves in a shell variable, over every document. A jq runtime error prints jq's message
    with `error_line` as the input line and exits 5."""
    pieces = []
    for document in documents:
        try:
            pieces.append(raw_text(extract(document)))
        except JqError as error:
            sys.stderr.write(f"jq: error (at <stdin>:{error_line}): {error}\n")
            sys.exit(5)
    return "\n".join(pieces).rstrip("\n")


def jq_str(value):
    """What `jq -r '.x // ""'` prints, with the trailing newlines a shell $(...) drops."""
    if value is None or value is False:
        return ""
    return raw_text(value).rstrip("\n")


def jq_field(root, *keys, default=None):
    """jq -r '.a.b // default'. EMPTY_INPUT makes jq print nothing, so the field is empty even with a default.
    Only a missing, null or false value takes the default; an empty string stays empty."""
    if root is EMPTY_INPUT:
        return ""
    value = jq_get(root, *keys)
    if default is not None and not truthy(value):
        return default
    return jq_str(value)


def tool_input_of(payload):
    """The payload's tool_input object, or None when it has none."""
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    return tool_input if isinstance(tool_input, dict) else None


def edited_file_path(tool_input):
    """`jq -r '.file_path // empty'` on tool_input, without trailing newlines; "" when it names no file."""
    file_path = tool_input.get("file_path")
    if not truthy(file_path):
        return ""
    return file_path.rstrip("\n") if isinstance(file_path, str) else json.dumps(file_path)


def read_file_text(path, errors="surrogateescape"):
    """A file's text decoded as UTF-8, or None when it cannot be read."""
    try:
        with open(path, "rb") as handle:
            file_bytes = handle.read()
    except OSError:
        return None
    return file_bytes.decode("utf-8", errors)


def prune_old_state_files(state_dir):
    """find state_dir -type f -mtime +2 -delete"""
    now = time.time()
    for directory, _, names in os.walk(state_dir):
        for name in names:
            path = os.path.join(directory, name)
            try:
                if os.path.islink(path) or not os.path.isfile(path):
                    continue
                if int((now - os.stat(path).st_mtime) // 86400) > STATE_MAX_AGE_DAYS:
                    os.unlink(path)
            except OSError:
                pass


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


def temp_roots():
    """The real paths of the directories that count as temp: /tmp, /var/tmp, the system temp dir and $TMPDIR."""
    roots = {"/tmp", "/var/tmp", tempfile.gettempdir()}
    if os.environ.get("TMPDIR"):
        roots.add(os.environ["TMPDIR"])
    return [os.path.realpath(root) for root in roots]


def is_under_temp_dir(path):
    real = os.path.realpath(path)
    return any(real == root or real.startswith(root.rstrip("/") + "/") for root in temp_roots())


def expand_env_names(text, names):
    """The text with `$NAME` and `${NAME}` replaced by the environment value, for each NAME in names that is set.
    Other variables stay as written."""
    for name in names:
        value = os.environ.get(name)
        if value is None:
            continue
        text = re.sub(r"\$\{" + name + r"\}|\$" + name + r"(?!\w)", lambda _found, value=value: value, text)
    return text


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
        with contextlib.suppress(Exception):
            emit_stderr(f"{hook_name()}: crashed ({type(error).__name__}: {error}) - blocking the call\n")
        sys.exit(2)
    sys.exit(code or 0)
