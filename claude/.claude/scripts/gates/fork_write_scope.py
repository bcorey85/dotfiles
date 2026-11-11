#!/usr/bin/env python3
"""PreToolUse hook on Write: the code-fork agent writes only files inside a run folder.

code-fork runs the /code, /review and /fix steps. A coder makes every repo edit; the fork writes only its own
handoff and stop files in the run folder, `git rev-parse --git-path code-phase`: a `code-phase` directory whose
parent is a git directory (it holds a HEAD file). A shell heredoc cannot carry that text, because the safety gate
reads a heredoc's body as command text. Any other agent, and the main session, passes untouched.

The fork also cannot write the run folder's review-stop.md while the fix state holds `asks_launch_pending`: the fix
run that asks-done printed has not launched yet.

Fail-closed for code-fork: an error while judging its call denies the Write and names the gate. Any other payload
exits before anything can fail. hook_input loads only for a code-fork call: its imports triple the hook's time, and
every Write in every session runs this hook.
"""
import json
import os
import pathlib
import sys

GATED_AGENT = "code-fork"
RUN_FOLDER_NAME = "code-phase"
DENY_TEXT = ("code-fork writes only files in its run folder, the path `git rev-parse --path-format=absolute "
             "--git-path code-phase` prints. {file_path} is outside it. Send any other edit to a coder.")
PENDING_TEXT = ("asks-done printed a fix run that has not launched, so review-stop.md cannot be written yet. Run "
                "this launch line first, then wait on it: {launch_line} If this run must not start, stop and tell the "
                "user, who removes the `{key}` key from {state_file}.")
UNREADABLE_STATE_TEXT = ("fork_write_scope: {state_file} is not a readable JSON object ({error}), so review-stop.md "
                         "cannot be written. Tell the user to repair or delete that file - denied.")
ERROR_TEXT = "fork_write_scope: could not judge the Write ({error}) - denied."
LIB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")


def add_lib_to_path():
    """Puts lib on sys.path once."""
    if LIB_DIR not in sys.path:
        sys.path.insert(0, LIB_DIR)


def in_run_folder(file_path):
    """True when file_path sits under a `code-phase` directory whose parent holds a git HEAD file."""
    resolved = pathlib.Path(file_path).expanduser().resolve()
    for ancestor in resolved.parents:
        if ancestor.name != RUN_FOLDER_NAME:
            continue
        git_head = ancestor.parent / "HEAD"
        if git_head.is_file():
            return True
    return False


def load_stop_and_state_owners():
    """The modules that own the stop file name and the fix state names. They load only for a code-fork write
    inside a run folder."""
    add_lib_to_path()
    import review_fix_names
    import stop_file_names
    return stop_file_names, review_fix_names


def pending_launch_reason(file_path):
    """The deny text when file_path is the run folder's review-stop.md and the fix state holds an unlaunched fix
    run, else None. The run folder's parent is the git dir, which also holds the fix state."""
    stop_file_names, review_fix_names = load_stop_and_state_owners()
    resolved = pathlib.Path(file_path).expanduser().resolve()
    if resolved.name != stop_file_names.REVIEW_STOP_FILE or resolved.parent.name != RUN_FOLDER_NAME:
        return None
    state_file = resolved.parent.parent / review_fix_names.REVIEW_FIX_FOLDER / review_fix_names.STATE_FILE_NAME
    if not state_file.is_file():
        return None
    try:
        state = json.loads(state_file.read_text())
    except ValueError as error:
        return UNREADABLE_STATE_TEXT.format(state_file=state_file, error=error)
    if not isinstance(state, dict):
        return UNREADABLE_STATE_TEXT.format(state_file=state_file, error="top level is not an object")
    launch_line = state.get(review_fix_names.PENDING_LAUNCH_KEY)
    if not launch_line:
        return None
    return PENDING_TEXT.format(launch_line=launch_line, key=review_fix_names.PENDING_LAUNCH_KEY,
                               state_file=state_file)


def load_hook_input():
    add_lib_to_path()
    import hook_input
    return hook_input


def write_deny_reason(payload, hook_input):
    """The deny text for a code-fork Write outside a run folder, or for review-stop.md in the run folder while a
    fix launch is pending, else None."""
    tool_input = hook_input.tool_input_of(payload) or {}
    file_path = hook_input.edited_file_path(tool_input)
    if file_path and in_run_folder(file_path):
        return pending_launch_reason(file_path)
    return DENY_TEXT.format(file_path=file_path or "The Write names no file and")


def main():
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return 0
    stdin_text = sys.stdin.buffer.read().decode("utf-8", "replace")
    payload = json.loads(stdin_text)
    if not isinstance(payload, dict) or payload.get("agent_type") != GATED_AGENT:
        return 0

    hook_input = load_hook_input()
    try:
        reason = write_deny_reason(payload, hook_input)
    except Exception as error:
        reason = ERROR_TEXT.format(error=error)
    if reason:
        hook_input.emit_decision("deny", reason)
    return 0


if __name__ == "__main__":
    # A crash before the code-fork check (unreadable stdin) exits 0 with a stderr line: fail-open for every caller,
    # since only code-fork is gated and its own path is fail-closed above.
    try:
        exit_code = main()
    except Exception as crash:
        sys.stderr.write(f"fork_write_scope: could not read the hook input ({crash})\n")
        exit_code = 0
    sys.exit(exit_code)
