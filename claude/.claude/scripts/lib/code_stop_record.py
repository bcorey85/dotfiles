"""The last /code stop a session relayed: which run folder it is in, so a resume from another checkout finds it."""
import pathlib
import sys
import time

import script_utils

# One file per session under the home's .claude.
STOP_RECORD_DIR = ".claude/code-stop-sessions"

TEXT_KEYS = ("runFolder", "repoTop", "goOn")
RECORD_KEYS = (*TEXT_KEYS, "time")


def stop_record_dir():
    # Read at call time: the tests patch HOME.
    return pathlib.Path.home() / STOP_RECORD_DIR


def stop_record_path(session):
    return script_utils.session_state_path(stop_record_dir(), session)


def record_stop(session, run_folder, repo_top, go_on):
    """Save the run folder, repo top and `To go on:` line (None for a finished stop) of the stop `session` relayed,
    replacing its earlier record. No session id, no record."""
    record = {"runFolder": str(run_folder), "repoTop": str(repo_top), "goOn": go_on or "", "time": time.time()}
    script_utils.write_session_state(stop_record_dir(), session, record)


def last_stop(session):
    """{"runFolder", "repoTop", "goOn", "time"} of the session's last relayed stop; goOn is "" for a finished stop.
    None for no session id or no record.
    Fail-open: a record that cannot be read is reported on stderr and reads as no record."""
    error_prefix = "code_stop_record: ignoring"
    record = script_utils.read_session_state(stop_record_dir(), session, error_prefix)
    if record is None:
        return None

    for key in RECORD_KEYS:
        if key not in record:
            print(f"{error_prefix} {stop_record_path(session)}: {key!r}", file=sys.stderr)
            return None

    for key in TEXT_KEYS:
        if not isinstance(record[key], str):
            print(f"{error_prefix} {stop_record_path(session)}: bad {key}", file=sys.stderr)
            return None

    # bool is an int subclass, but never a timestamp.
    if isinstance(record["time"], bool) or not isinstance(record["time"], (int, float)):
        print(f"{error_prefix} {stop_record_path(session)}: bad time", file=sys.stderr)
        return None
    return {key: record[key] for key in RECORD_KEYS}
