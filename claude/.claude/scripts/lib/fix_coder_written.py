"""The untracked paths the review loop's fix coder wrote, kept in <git dir>/code-phase/fix-coder-written.json.

The loop runs its fix coder as `claude -p`, which leaves no subagent transcript, so this record is the only way to tell
that coder's new files from another session's. The loop adds to it (`add_paths`); code_review_start.py reads it
(`recorded`) and reviews a recorded path as the run's own; review_loop_untracked.guarded_untracked reads it and
leaves a recorded path deletable across loop processes; phase_start.py `--new-run` empties it (`clear`).
"""
import json

import script_utils

RECORD_FILE = "fix-coder-written.json"


def record_file(repo):
    """The record's path, or None when git cannot name the repo's git dir."""
    folder = script_utils.git_path(repo, "code-phase")
    if folder is None:
        return None
    return folder / RECORD_FILE


def recorded(repo):
    """The set of recorded paths; empty when there is no record or it does not parse."""
    file = record_file(repo)
    if file is None or not file.is_file():
        return set()
    try:
        return set(json.loads(file.read_text()))
    except (OSError, ValueError, TypeError):
        return set()


def add_paths(repo, paths):
    """Adds `paths` to the record. A repo with no git dir records nothing."""
    file = record_file(repo)
    if file is None or not paths:
        return
    file.parent.mkdir(exist_ok=True)
    script_utils.write_text_atomically(file, json.dumps(sorted(recorded(repo) | set(paths))) + "\n")


def clear(repo):
    """Empties the record: a new run starts with no fix coder files."""
    file = record_file(repo)
    if file is not None:
        file.unlink(missing_ok=True)
