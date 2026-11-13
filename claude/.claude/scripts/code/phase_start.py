#!/usr/bin/env python3
"""Record the tree a /code run starts from (kept across the run's phases at one HEAD), and print the HEAD sha, which
is the phase base.

    python3 ~/.claude/scripts/code/phase_start.py [--new-run]

Run from the repo root before the phase's coder dispatch. Writes <git dir>/code-phase/start.json:
{"head": <sha>, "dirty": {<path>: <sha-256 of its bytes, or null when gone>}} for every file dirty or untracked now.
code_review_start.py reads it: a file dirty here that holds the same bytes at review time is held by another session,
so the review loop never reviews or edits it.
The record is of the run's start, not of each phase: `--new-run` replaces it. Without the flag an existing record
whose head is the current HEAD is kept, so the files an earlier phase of the run left dirty stay the run's own. A
missing record, or one for another HEAD, is replaced either way. Prints the HEAD sha.
An existing <git dir>/code-phase/stop.md is renamed to stop.prev.md first (review-stop.md stays).
"""
import json
import os
import pathlib
import sys

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(SCRIPTS_DIR / folder) for folder in ("lib", "code")]

import script_utils
import stop_file_names
import worktree_snapshot
from code_wait import phase_dir

START_FILE = "start.json"
COMMAND = "python3 ~/.claude/scripts/code/phase_start.py"


class StartRecordError(ValueError):
    """A start record that is missing a field or names another phase base."""


def start_record(repo):
    """{"head", "dirty"} of the repo now."""
    head = script_utils.head_commit(repo)
    if head is None:
        raise StartRecordError(f"{repo} has no HEAD commit, so the phase has no base")

    root = pathlib.Path(repo)
    codes = worktree_snapshot.status_codes(root)
    dirty = {path: worktree_snapshot.file_hash(root, path) for path in sorted(codes)}
    return {"head": head, "dirty": dirty}


def read_start_record(repo):
    """The start record on disk as {"head", "dirty"}; None when there is no file. A record that does not parse raises
    StartRecordError."""
    record_file = phase_dir(repo) / START_FILE
    if not record_file.is_file():
        return None

    try:
        record = json.loads(record_file.read_text())
        return {"head": record["head"], "dirty": record["dirty"]}
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise StartRecordError(f"{record_file}: {error}; expected {{\"head\": <sha>, \"dirty\": {{<path>: <hash>}}}}. "
                               "Re-run phase_start.py before the next coder dispatch.") from error


def unchanged_dirty_files(repo, base_commit):
    """The files dirty when the run started (the kept start record) that hold the same bytes now: another session's,
    not the run's. None when no start record exists. A record for another base, or one that does not parse, raises
    StartRecordError."""
    record = read_start_record(repo)
    if record is None:
        return None

    head, dirty = record["head"], record["dirty"]
    record_file = phase_dir(repo) / START_FILE
    if head != base_commit:
        raise StartRecordError(f"{record_file} records phase base {head}, not {base_commit}: phase_start.py did not "
                               f"run before this phase's coder. Run `{COMMAND}` before each phase's coder dispatch "
                               "and pass the sha it prints as --base.")

    root = pathlib.Path(repo)
    return sorted(path for path, saved in dirty.items() if worktree_snapshot.file_hash(root, path) == saved)


def move_stale_stop_aside(folder):
    """Rename <folder>/stop.md to stop.prev.md, replacing an older one, so the fork's next stop is a new file: the
    Write tool refuses an existing file the fork has not read. A failed rename is reported and the script goes on."""
    stop_file = folder / stop_file_names.STOP_FILE
    if not stop_file.is_file():
        return

    previous_file = folder / stop_file_names.PREVIOUS_STOP_FILE
    try:
        os.replace(stop_file, previous_file)
    except OSError as error:
        print(f"phase_start: could not move {stop_file} to {previous_file}: {error}", file=sys.stderr)


def main():
    unknown = [arg for arg in sys.argv[1:] if arg != "--new-run"]
    if unknown:
        sys.exit(f"phase_start: unknown argument {unknown[0]}\nusage: phase_start.py [--new-run]")

    repo = script_utils.repo_root(pathlib.Path.cwd())
    if repo is None:
        sys.exit(f"phase_start: {pathlib.Path.cwd()} is not inside a git work tree")

    move_stale_stop_aside(phase_dir(repo))

    try:
        record = start_record(repo)
    except StartRecordError as error:
        sys.exit(f"phase_start: {error}")

    try:
        kept = read_start_record(repo)
    except StartRecordError as error:
        print(f"phase_start: replacing the bad start record: {error}", file=sys.stderr)
        kept = None
    if "--new-run" not in sys.argv[1:] and kept is not None and kept["head"] == record["head"]:
        print(record["head"])
        return 0

    folder = phase_dir(repo)
    folder.mkdir(exist_ok=True)
    script_utils.write_text_atomically(folder / START_FILE, json.dumps(record, indent=2) + "\n")
    print(record["head"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
