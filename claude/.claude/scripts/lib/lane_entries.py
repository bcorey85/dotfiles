"""lane_entries.py: owns the lane files (`<state>/herdr-lanes/<name>.json`, one JSON file per lane) and the lane
lock, and is the only reader and writer of both.

A lane is a worktree started for another Claude session. Its file is `<lanes_dir>/<name>.json` and holds the fields in
`FIELDS`, plus `base_commit` when one was recorded, so a lane can be resumed or closed later. Every write holds the
one lock `lane_lock_path()` names. Standard library, `file_lock` and `script_utils`."""
import contextlib
import datetime
import json
import os
import pathlib
import re

import file_lock
import script_utils

LOCK_TIMEOUT_SECONDS = 10
FIELDS = ("name", "worktree", "main_checkout", "branch", "brief", "session_id", "reports_to", "started_at")
OPTIONAL_FIELDS = ("base_commit",)
NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
STARTED_AT_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")
COMMIT_ID_PATTERN = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


class LaneFileError(Exception):
    """A lane file, or an entry about to be written, that the grammar refuses. Names the file, the field and the
    form the field must have."""

    def __init__(self, file, field, expected):
        self.file = file
        self.field = field
        self.expected = expected
        super().__init__(f"{file}: field {field}: expected {expected}")


class LaneExistsError(Exception):
    """An entry of that name exists and its worktree folder is still there."""

    def __init__(self, name, file):
        super().__init__(f"lane {name} already exists with a live worktree ({file})")


class LaneNotFoundError(Exception):
    """No entry has that name."""

    def __init__(self, name):
        super().__init__(f"no lane named {name}")


def lanes_dir():
    """`${XDG_STATE_HOME:-$HOME/.local/state}/herdr-lanes`."""
    return script_utils.xdg_state_home() / "herdr-lanes"


def lane_lock_path():
    """The one lock file every write holds."""
    return lanes_dir() / "lanes.lock"


def lane_file(name):
    """The file of the lane `name`. Raises LaneFileError for a name that is not a valid lane name."""
    file = lanes_dir() / f"{name}.json"
    if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
        raise LaneFileError(file, "name", "letters, digits, '.', '_' or '-', starting with a letter or digit")
    return file


def _is_absolute_path(value):
    return isinstance(value, str) and os.path.isabs(value)


def _is_non_empty_text(value):
    return isinstance(value, str) and value != ""


def _is_text(value):
    return isinstance(value, str)


def _is_iso_with_offset(value):
    if not isinstance(value, str) or not STARTED_AT_PATTERN.fullmatch(value):
        return False
    try:
        datetime.datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_commit_id(value):
    return isinstance(value, str) and COMMIT_ID_PATTERN.fullmatch(value) is not None


FIELD_RULES = {
    "name": (_is_non_empty_text, "a lane name equal to the file name"),
    "worktree": (_is_absolute_path, "an absolute path"),
    "main_checkout": (_is_absolute_path, "an absolute path"),
    "branch": (_is_non_empty_text, "a non-empty string"),
    "brief": (_is_non_empty_text, "a non-empty string"),
    "session_id": (_is_text, "a string, empty until filled"),
    "reports_to": (_is_text, "a string, empty when no session started the lane"),
    "started_at": (_is_iso_with_offset, "an ISO-8601 time with offset, to the second"),
    "base_commit": (_is_commit_id, "a full lowercase hex commit id (40 or 64 digits)"),
}


def validate_entry(data, file):
    """Raises LaneFileError unless `data` is a lane entry that belongs in `file`."""
    if not isinstance(data, dict):
        raise LaneFileError(file, "(file)", "a JSON object")

    for field in FIELDS:
        if field not in data:
            raise LaneFileError(file, field, "present")

    allowed = FIELDS + OPTIONAL_FIELDS
    for field in sorted(data):
        if field not in allowed:
            raise LaneFileError(file, field, f"no such field (allowed: {', '.join(allowed)})")

    for field in allowed:
        if field not in data:
            continue
        is_valid, expected = FIELD_RULES[field]
        if not is_valid(data[field]):
            raise LaneFileError(file, field, expected)

    if not NAME_PATTERN.fullmatch(data["name"]) or data["name"] != pathlib.Path(file).stem:
        raise LaneFileError(file, "name", "a lane name equal to the file name")


def _unreadable_error(location, field, noun, error):
    """The LaneFileError for a file or folder that cannot be read."""
    reason = error.strerror or error
    return LaneFileError(location, field, f"a readable {noun} ({reason})")


def _unreadable_file_error(file, error):
    """The LaneFileError for a file that cannot be read."""
    return _unreadable_error(file, "(file)", "file", error)


def read_entry(file):
    """The entry in `file`: the one grammar. Raises LaneFileError for anything unreadable or malformed, and lets
    FileNotFoundError through so a reader can tell a file that vanished from a bad one."""
    try:
        text = pathlib.Path(file).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise
    except UnicodeDecodeError as error:
        raise LaneFileError(file, "(file)", "UTF-8 text") from error
    except OSError as error:
        raise _unreadable_file_error(file, error) from error

    try:
        data = json.loads(text)
    except ValueError as error:
        raise LaneFileError(file, "(file)", f"valid JSON ({error})") from error

    validate_entry(data, file)
    return data


def read_named_entry(file):
    """`read_entry` for a file the caller named: a missing file is a LaneFileError too."""
    try:
        return read_entry(file)
    except FileNotFoundError as error:
        raise _unreadable_file_error(file, error) from error


def entry_files():
    """Every lane file, in file name order; empty when the folder is missing. Raises LaneFileError when the folder
    exists and cannot be read."""
    folder = lanes_dir()
    try:
        names = os.listdir(folder)
    except FileNotFoundError:
        return []
    except OSError as error:
        raise _unreadable_error(folder, "(folder)", "folder", error) from error
    return sorted(folder / name for name in names if name.endswith(".json"))


def all_entries():
    """Every entry, sorted by name."""
    entries = []
    for file in entry_files():
        try:
            entries.append(read_entry(file))
        except FileNotFoundError:
            continue  # removed by another session after the folder was listed
    return sorted(entries, key=lambda lane: lane["name"])


def is_lane_session(session_id):
    """True when a lane entry holds `session_id`; an empty id (a lane not yet filled) is no session. Raises what
    `all_entries` raises."""
    if not session_id:
        return False
    return any(lane["session_id"] == session_id for lane in all_entries())


def entry(name):
    """The entry named `name`, or None when it has no file."""
    file = lane_file(name)
    try:
        return read_entry(file)
    except FileNotFoundError:
        return None


def entry_containing(path):
    """The entry whose worktree is `path` or holds it (real paths), or None."""
    target = os.path.realpath(path)
    for lane in all_entries():
        worktree = os.path.realpath(lane["worktree"])
        if script_utils.path_is_under(target, worktree):
            return lane
    return None


@contextlib.contextmanager
def _locked():
    lanes_dir().mkdir(parents=True, exist_ok=True)
    with file_lock.hold_exclusive(lane_lock_path(), LOCK_TIMEOUT_SECONDS):
        yield


def _write(lane):
    file = lane_file(lane["name"])
    validate_entry(lane, file)
    script_utils.write_text_atomically(file, json.dumps(lane, indent=2) + "\n")


def _existing_entry(name):
    """The entry named `name`; the caller holds the lock. Raises LaneNotFoundError when there is none."""
    lane = entry(name)
    if lane is None:
        raise LaneNotFoundError(name)
    return lane


def add_entry(name, worktree, main_checkout, branch, brief, reports_to, base_commit=None):
    """Write a new entry with an empty session id and return it. `base_commit`, the commit the branch started from,
    is stored only when given. Raises LaneExistsError when an entry of that name
    has a worktree folder that exists; an entry whose folder is gone is replaced."""
    lane = {
        "name": name,
        "worktree": worktree,
        "main_checkout": main_checkout,
        "branch": branch,
        "brief": brief,
        "session_id": "",
        "reports_to": reports_to,
        "started_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    if base_commit is not None:
        lane["base_commit"] = base_commit
    with _locked():
        existing = entry(name)
        if existing is not None and pathlib.Path(existing["worktree"]).exists():
            raise LaneExistsError(name, lane_file(name))
        _write(lane)
    return lane


def set_session(name, session_id, brief=None):
    """Set the session id, and the brief when one is given. True when the file changed. Raises LaneNotFoundError."""
    with _locked():
        lane = _existing_entry(name)
        updated = dict(lane, session_id=session_id)
        if brief is not None:
            updated["brief"] = brief
        if updated == lane:
            return False
        _write(updated)
    return True


def remove_entry(name):
    """Delete the entry and return it. Raises LaneNotFoundError."""
    with _locked():
        lane = _existing_entry(name)
        lane_file(name).unlink()
    return lane
