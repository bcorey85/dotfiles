#!/usr/bin/env python3
"""Record the tree a /code phase starts from, and print the HEAD sha, which is the phase base.

    python3 ~/.claude/scripts/code/phase_start.py

Run from the repo root before the phase's coder dispatch. Writes <git dir>/code-phase/start.json:
{"head": <sha>, "dirty": {<path>: <sha-256 of its bytes, or null when gone>}} for every file dirty or untracked now.
code_review_start.py reads it: a file dirty here that holds the same bytes at review time is held by another session,
so the review loop never reviews or edits it.
"""
import json
import pathlib
import sys

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(SCRIPTS_DIR / folder) for folder in ("lib", "code")]

import script_utils
import worktree_snapshot
from code_wait import phase_dir

START_FILE = "start.json"
COMMAND = "python3 ~/.claude/scripts/code/phase_start.py"


class StartRecordError(ValueError):
    """A start record that is missing a field or names another phase base."""


def start_record(repo):
    """{"head", "dirty"} of the repo now."""
    head = script_utils.git_output(repo, "rev-parse", "--verify", "-q", "HEAD")
    if head is None:
        raise StartRecordError(f"{repo} has no HEAD commit, so the phase has no base")

    root = pathlib.Path(repo)
    codes = worktree_snapshot.status_codes(root)
    dirty = {path: worktree_snapshot.file_hash(root, path) for path in sorted(codes)}
    return {"head": head.strip(), "dirty": dirty}


def unchanged_dirty_files(repo, base_commit):
    """The files dirty at the phase start that hold the same bytes now: another session's, not the phase's. None when
    no start record exists. A record for another base, or one that does not parse, raises StartRecordError."""
    record_file = phase_dir(repo) / START_FILE
    if not record_file.is_file():
        return None

    try:
        record = json.loads(record_file.read_text())
        head, dirty = record["head"], record["dirty"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise StartRecordError(f"{record_file}: {error}; expected {{\"head\": <sha>, \"dirty\": {{<path>: <hash>}}}}. "
                               "Re-run phase_start.py before the next coder dispatch.") from error
    if head != base_commit:
        raise StartRecordError(f"{record_file} records phase base {head}, not {base_commit}: phase_start.py did not "
                               f"run before this phase's coder. Run `{COMMAND}` before each phase's coder dispatch "
                               "and pass the sha it prints as --base.")

    root = pathlib.Path(repo)
    return sorted(path for path, saved in dirty.items() if worktree_snapshot.file_hash(root, path) == saved)


def main():
    repo = script_utils.repo_root(pathlib.Path.cwd())
    if repo is None:
        sys.exit(f"phase_start: {pathlib.Path.cwd()} is not inside a git work tree")

    try:
        record = start_record(repo)
    except StartRecordError as error:
        sys.exit(f"phase_start: {error}")

    folder = phase_dir(repo)
    folder.mkdir(exist_ok=True)
    script_utils.write_text_atomically(folder / START_FILE, json.dumps(record, indent=2) + "\n")
    print(record["head"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
