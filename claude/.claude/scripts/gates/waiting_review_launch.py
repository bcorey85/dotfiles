#!/usr/bin/env python3
"""SessionStart hook (compact, resume): tell the main session about a review loop that waits on its reviewers.

`review_fix.py launch` hands each round's reviewers to the main session with `ACTION: dispatch-reviewer`. When the
conversation is compacted after that line, the session can lose it, and the loop waits on reports nobody writes. This
hook prints the open dispatch lines of every launch run of the session's repo whose loop still runs, as
additionalContext. It prints nothing for an `--agent` seat, outside a repo, or when no loop waits.

Fail-open: an unreadable event or a bad manifest prints a warning on stderr and no context, since a missed reminder
costs less than a blocked session start. Always exits 0.
"""
import json
import pathlib
import sys

_SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(_SCRIPTS_DIR / "lib"), str(_SCRIPTS_DIR / "review")]
import hook_input
import reviewer_dispatch
import script_utils

HEADER = ("A review loop launched earlier in this session still waits on its reviewers. Do these steps now, as "
          "`/review` step 1 says:")


def session_start_event():
    """The hook event as a dict, or None when it cannot be read."""
    try:
        event = json.loads(hook_input.read_stdin_text() or "{}")
    except (OSError, ValueError) as error:
        hook_input.emit_stderr(f"waiting_review_launch: cannot read the hook event ({error}); no reminder\n")
        return None
    if not isinstance(event, dict):
        return None
    return event


def main():
    event = session_start_event()
    if event is None or event.get("agent_type"):
        return 0

    repo = script_utils.repo_root(event.get("cwd") or ".")
    if repo is None:
        return 0
    try:
        lines = reviewer_dispatch.waiting_launch_lines(repo)
    except reviewer_dispatch.ManifestError as error:
        hook_input.emit_stderr(f"waiting_review_launch: {error}; no reminder\n")
        return 0
    if not lines:
        return 0

    context = "\n".join([HEADER, *lines])
    document = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}
    print(json.dumps(document, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
