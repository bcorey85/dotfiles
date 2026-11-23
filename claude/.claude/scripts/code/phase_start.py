#!/usr/bin/env python3
"""Record the tree a /code run starts from (kept across the run's phases at one HEAD), and print the phase base (HEAD,
or the kept record's head under --resume).

    python3 ~/.claude/scripts/code/phase_start.py [--new-run | --resume]

Run from the repo root before the phase's coder dispatch. Writes <git dir>/code-phase/start.json, once per call:
{"head": <sha>, "dirty": {<path>: <sha-256 of its bytes, or null when gone>}, "holder": {"session", "cwd"} | null,
"sessions": [<session id>, ...], "started_at": <epoch seconds> | null}. `dirty` lists every file dirty or untracked
now; `holder` is the live session other than the run's that works in the repo now; `sessions` are the run's session
ids (a resume adds its own). code_review_start.py reads it: with a holder recorded, every file dirty here is held for
the whole phase, and one whose bytes changed is named as a tool fault; with no holder, a file dirty here that holds the
same bytes at review time is held while another live session works in the repo.
The record is of the run's start, not of each phase: `--new-run` replaces it. Without the flag an existing record
whose head is the current HEAD is kept, so the files an earlier phase of the run left dirty stay the run's own. A
missing record, or one for another HEAD, is replaced either way. Prints the HEAD sha, except under --resume (below).
`--resume` is for a run that went on after a stop, where the user may have committed the phase since: when the
kept record's head is an ancestor of HEAD, the record is kept and its head is printed as the phase base. With no
record, or a head that is not an ancestor, it prints HEAD as without the flag and says so on stderr.
Before anything is moved, `--resume` exits non-zero when this repo's run folder holds no stop.md and no stop.prev.md
newer than the session's last relayed stop (lib/code_stop_record.py), and that stop is in another run folder: it
names both and the stop's recorded `To go on:` line (`/code resume <repo top>` for a finished stop).
An existing <git dir>/code-phase/stop.md is renamed to stop.prev.md first (review-stop.md stays), and an existing
handoff.txt to handoff.prev.txt, so a review start never reads an earlier phase's hand-off as this phase's; loop-dir
goes to loop-dir.prev, so a wait never returns an earlier phase's packet before this phase's review starts.
"""
import json
import os
import pathlib
import sys
import time

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(SCRIPTS_DIR / folder) for folder in ("lib", "code")]

import code_stop_record
import code_wait
import script_utils
import session_registry
import stop_file_names
import worktree_snapshot

START_FILE = "start.json"
COMMAND = "python3 ~/.claude/scripts/code/phase_start.py"


class StartRecordError(ValueError):
    """A start record that is missing a field or names another phase base."""


RECORD_SHAPE = ('{"head": <sha>, "dirty": {<path>: <hash>}, "holder": {"session": <text>, "cwd": <text>} | null, '
                '"sessions": [<session id>], "started_at": <epoch seconds> | null}')


def current_holder(repo, own_session_id):
    """{"session", "cwd"} of the live session other than `own_session_id` that works in the repo now; None when there
    is none or the run's own session id is unknown."""
    if not own_session_id:
        return None
    row = session_registry.other_live_session_in(repo, own_session_id)
    if row is None:
        return None
    return {"session": session_registry.holder_label(row), "cwd": row["cwd"]}


def start_record(repo, own_session_id=""):
    """The start record of the repo now: head, dirty, holder, sessions and started_at."""
    head = script_utils.head_commit(repo)
    if head is None:
        raise StartRecordError(f"{repo} has no HEAD commit, so the phase has no base")

    root = pathlib.Path(repo)
    codes = worktree_snapshot.status_codes(root)
    dirty = {path: worktree_snapshot.file_hash(root, path) for path in sorted(codes)}
    return {"head": head, "dirty": dirty, "holder": current_holder(repo, own_session_id),
            "sessions": [own_session_id] if own_session_id else [], "started_at": time.time()}


def checked_record(record):
    """The five keys of a parsed record, with the defaults of a record written before holder, sessions and started_at
    existed. A key of the wrong type raises TypeError."""
    holder = record.get("holder")
    sessions = record.get("sessions", [])
    started_at = record.get("started_at")
    holder_ok = holder is None or (isinstance(holder, dict) and isinstance(holder.get("session"), str)
                                   and isinstance(holder.get("cwd"), str))
    started_ok = started_at is None or (isinstance(started_at, (int, float)) and not isinstance(started_at, bool))
    if not isinstance(record["dirty"], dict):
        raise TypeError("dirty is not an object")
    if not holder_ok:
        raise TypeError("holder is neither null nor an object with text session and cwd")
    if not (isinstance(sessions, list) and all(isinstance(entry, str) for entry in sessions)):
        raise TypeError("sessions is not a list of session ids")
    if not started_ok:
        raise TypeError("started_at is neither null nor a number")
    return {"head": record["head"], "dirty": record["dirty"], "holder": holder, "sessions": sessions,
            "started_at": started_at}


def read_start_record(repo):
    """The start record on disk with its five keys; None when there is no file. A record that does not parse, or holds
    a key of the wrong type, raises StartRecordError."""
    record_file = code_wait.phase_dir(repo) / START_FILE
    if not record_file.is_file():
        return None

    try:
        return checked_record(json.loads(record_file.read_text()))
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as error:
        raise StartRecordError(f"{record_file}: {error!r}; expected {RECORD_SHAPE}. "
                               "Re-run phase_start.py before the next coder dispatch.") from error


def base_relates_to_head(repo, base_commit, head):
    """Whether `base_commit` is the recorded head, an ancestor of it (a merge-base), or the current HEAD when the
    recorded head is an ancestor of it (a resume base)."""
    if script_utils.is_ancestor(repo, base_commit, head):
        return True
    if not script_utils.is_ancestor(repo, head, base_commit):
        return False
    return base_commit == script_utils.head_commit(repo)


def check_record_base(repo, base_commit, record):
    """Raises StartRecordError when the record's head is neither an ancestor nor a descendant of the base."""
    head = record["head"]
    record_file = code_wait.phase_dir(repo) / START_FILE
    if not base_relates_to_head(repo, base_commit, head):
        raise StartRecordError(f"{record_file} records phase base {head}, and {base_commit} is neither an ancestor of "
                               f"it nor the current HEAD it is an ancestor of. Pass --base {head} (a base may be an "
                               "ancestor of the recorded head, or HEAD when the recorded head is an ancestor of it). "
                               f"When phase_start.py did not run before this phase's coder, run `{COMMAND}` first.")


def changed_dirty_files(repo, record):
    """The paths of `record["dirty"]` whose bytes now differ from the recorded hash. A deleted file counts as changed
    unless it was recorded as gone."""
    root = pathlib.Path(repo)
    return sorted(path for path, saved in record["dirty"].items() if worktree_snapshot.file_hash(root, path) != saved)


def move_aside(folder, name, previous_name):
    """Rename <folder>/<name> to <previous_name>, replacing an older one, so the fork's next file of that name is new:
    the Write tool refuses an existing file the fork has not read. A failed rename is reported and the script goes
    on."""
    current_file = folder / name
    if not current_file.is_file():
        return

    previous_file = folder / previous_name
    try:
        os.replace(current_file, previous_file)
    except OSError as error:
        print(f"phase_start: could not move {current_file} to {previous_file}: {error}", file=sys.stderr)


def resume_base(repo, kept):
    """The phase base of a resume: the kept record's head when it is an ancestor of HEAD, else None."""
    if kept is None:
        print("phase_start: no start record to resume from; the phase base is HEAD.", file=sys.stderr)
        return None
    if not script_utils.is_ancestor(repo, kept["head"], "HEAD"):
        print(f"phase_start: the start record's head {kept['head']} is not an ancestor of HEAD; the phase base is "
              "HEAD.", file=sys.stderr)
        return None
    return kept["head"]


def other_run_refusal(run_folder):
    """The refusal text when this repo's run folder holds no stop of its own (no stop.md, and no stop.prev.md newer
    than the session's recorded stop) and that recorded stop is in another run folder; None otherwise. Fail-open: no
    session id or no record resumes as before."""
    if (run_folder / stop_file_names.STOP_FILE).is_file():
        return None

    recorded = code_stop_record.last_stop(os.environ.get("CLAUDE_CODE_SESSION_ID"))
    if recorded is None:
        return None
    previous_stop = run_folder / stop_file_names.PREVIOUS_STOP_FILE
    if previous_stop.is_file() and previous_stop.stat().st_mtime > recorded["time"]:
        return None
    if pathlib.Path(recorded["runFolder"]).resolve() == run_folder.resolve():
        return None
    resume_line = recorded["goOn"] or f"/code resume {recorded['repoTop']}"
    return (f"phase_start: --resume found no stop in {run_folder}, and this session's last stop is in "
            f"{recorded['runFolder']}. Resume that run from its repo: {resume_line}")


def kept_record(kept, fresh, own_session_id):
    """The kept record of the run's start with this call's additions: this session's id when missing, and the holder
    seen now when the kept record has none. head, dirty and started_at stay as recorded."""
    sessions = list(kept["sessions"])
    if own_session_id and own_session_id not in sessions:
        sessions.append(own_session_id)
    holder = kept["holder"] or fresh["holder"]
    return {**kept, "holder": holder, "sessions": sessions}


def write_record(repo, record):
    folder = code_wait.phase_dir(repo)
    folder.mkdir(exist_ok=True)
    script_utils.write_text_atomically(folder / START_FILE, json.dumps(record, indent=2) + "\n")


def main():
    flags = ("--new-run", "--resume")
    unknown = [arg for arg in sys.argv[1:] if arg not in flags]
    if unknown:
        sys.exit(f"phase_start: unknown argument {unknown[0]}\nusage: phase_start.py [--new-run | --resume]")
    if "--new-run" in sys.argv[1:] and "--resume" in sys.argv[1:]:
        sys.exit("phase_start: --new-run and --resume exclude each other\nusage: phase_start.py [--new-run | --resume]")

    repo = script_utils.repo_root(pathlib.Path.cwd())
    if repo is None:
        sys.exit(f"phase_start: {pathlib.Path.cwd()} is not inside a git work tree")

    run_folder = code_wait.phase_dir(repo)
    if "--resume" in sys.argv[1:]:
        refusal = other_run_refusal(run_folder)
        if refusal is not None:
            sys.exit(refusal)
    move_aside(run_folder, stop_file_names.STOP_FILE, stop_file_names.PREVIOUS_STOP_FILE)
    move_aside(run_folder, code_wait.HANDOFF_FILE, code_wait.PREVIOUS_HANDOFF_FILE)
    move_aside(run_folder, code_wait.LOOP_DIR_FILE, code_wait.PREVIOUS_LOOP_DIR_FILE)
    move_aside(run_folder, code_wait.SCOPE_FILE, code_wait.PREVIOUS_SCOPE_FILE)

    own_session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not own_session_id:
        print("phase_start: CLAUDE_CODE_SESSION_ID is not set, so no holder or session is recorded", file=sys.stderr)
    try:
        record = start_record(repo, own_session_id)
    except StartRecordError as error:
        sys.exit(f"phase_start: {error}")

    try:
        kept = read_start_record(repo)
    except StartRecordError as error:
        print(f"phase_start: replacing the bad start record: {error}", file=sys.stderr)
        kept = None
    if "--resume" in sys.argv[1:]:
        base = resume_base(repo, kept)
        if base is not None:
            write_record(repo, kept_record(kept, record, own_session_id))
            print(base)
            return 0
    if "--new-run" not in sys.argv[1:] and kept is not None and kept["head"] == record["head"]:
        write_record(repo, kept_record(kept, record, own_session_id))
        print(record["head"])
        return 0

    write_record(repo, record)
    print(record["head"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
