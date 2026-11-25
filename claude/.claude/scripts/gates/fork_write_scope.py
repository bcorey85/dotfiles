#!/usr/bin/env python3
"""PreToolUse hook on Write: the code-fork agent writes only files inside a run folder.

code-fork runs the /code, /review and /fix steps. A coder makes every repo edit; the fork writes only its own
handoff and stop files in the run folder, `git rev-parse --git-path code-phase`: a `code-phase` directory whose
parent is a git directory (it holds a HEAD file). A shell heredoc cannot carry that text, because the safety gate
reads a heredoc's body as command text. Any other agent, and the main session, passes untouched.

Its stop.md Write is denied once when the run is a /code resume whose source changed with no review loop started
(code/resume_review_gate.py).

The fork also cannot write review-stop.md of the run folder while the fix state holds
`asks_launch_pending`: the fix run that asks-done printed has not launched yet.

Fail-closed for code-fork: any crash while judging its call exits 2 and names the gate. Any other payload
exits before anything can fail. hook_input loads only for a code-fork call: its imports triple the hook's time, and
every Write in every session runs this hook.
"""
import json
import os
import pathlib
import sys

LIB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")
sys.path.insert(0, LIB_DIR)
import import_guard

GATED_AGENT = "code-fork"
RUN_FOLDER_NAME = "code-phase"
GATE_NAME = "fork-write-scope"
DENY_TEXT = (f"{GATE_NAME}: code-fork writes only files in its run folder, the path `git rev-parse "
             "--path-format=absolute --git-path code-phase` prints. {file_path} is outside it. Send any other edit "
             "to a coder.")
REVIEW_FIX_ROUTE_TEXT = (
    DENY_TEXT + " To add findings to the fix run asks-done printed, write them to {findings_file} (the same `- ` item "
    "format) and add `--also-fix {findings_file}` to that launch line. The write gate stays closed: no other file "
    "outside the run folder can be written.")
PENDING_TEXT = (f"{GATE_NAME}: asks-done printed a fix run that has not launched, so {{file_name}} cannot be written "
                "yet. Run this launch line first, then wait on it: {launch_line} If this run must not start, stop and "
                "tell the user, who removes the `{key}` key from {state_file}.")
UNREADABLE_STATE_TEXT = (f"{GATE_NAME}: {{state_file}} is not a readable JSON object ({{error}}), so {{file_name}} "
                         "cannot be written. Tell the user to repair or delete that file - denied.")


def git_dir_folder(file_path, folder_name):
    """The ancestor folder of file_path named `folder_name` whose parent holds a git HEAD file (so the parent is a git
    dir), or None."""
    resolved = pathlib.Path(file_path).expanduser().resolve()
    for ancestor in resolved.parents:
        if ancestor.name != folder_name:
            continue
        if (ancestor.parent / "HEAD").is_file():
            return ancestor
    return None


def in_run_folder(file_path):
    """True when file_path sits under a `code-phase` directory whose parent holds a git HEAD file."""
    return git_dir_folder(file_path, RUN_FOLDER_NAME) is not None


def load_stop_and_state_owners():
    """The modules that own the stop file names and the fix state names. They load on every
    code-fork Write that names a path."""
    import review_fix_names
    import stop_file_names
    return stop_file_names, review_fix_names


def pending_launch_reason(file_path):
    """The deny text when file_path is review-stop.md of the run folder (which the relay hands to the user)
    and the fix state holds an unlaunched fix run, else None. The run folder's parent is the git dir,
    which also holds the fix state."""
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
        return UNREADABLE_STATE_TEXT.format(file_name=resolved.name, state_file=state_file, error=error)
    if not isinstance(state, dict):
        return UNREADABLE_STATE_TEXT.format(file_name=resolved.name, state_file=state_file,
                                            error="top level is not an object")
    launch_line = state.get(review_fix_names.PENDING_LAUNCH_KEY)
    if not launch_line:
        return None
    return PENDING_TEXT.format(file_name=resolved.name, launch_line=launch_line,
                               key=review_fix_names.PENDING_LAUNCH_KEY, state_file=state_file)


def resume_review_reason(file_path):
    """The deny text when file_path is stop.md of the run folder and a /code resume changed source with no review loop
    started, else None. Fail-open with no resume record (the run is not a resume); a crash in the check propagates to
    main, which fails closed and names the gate."""
    stop_file_names = load_stop_and_state_owners()[0]
    resolved = pathlib.Path(file_path).expanduser().resolve()
    if resolved.name != stop_file_names.STOP_FILE or resolved.parent.name != RUN_FOLDER_NAME:
        return None
    sys.path.insert(0, os.path.join(os.path.dirname(LIB_DIR), "code"))
    import resume_review_gate
    return resume_review_gate.resume_deny_reason(resolved)


def review_fix_route_reason(file_path):
    """The deny text when file_path sits under `<git dir>/review-fix/`, which names the route for findings the fix run
    should also apply, else None. The gate stays fail-closed: the Write is still denied."""
    review_fix_names = load_stop_and_state_owners()[1]
    review_fix_folder = git_dir_folder(file_path, review_fix_names.REVIEW_FIX_FOLDER)
    if review_fix_folder is None:
        return None
    run_folder = review_fix_folder.parent / RUN_FOLDER_NAME
    findings_file = run_folder / review_fix_names.RUN_FOLDER_FINDINGS_NAME
    return REVIEW_FIX_ROUTE_TEXT.format(file_path=file_path, findings_file=findings_file)


def write_deny_reason(payload, hook_input):
    """The deny text for a code-fork Write outside a run folder, or for review-stop.md
    in the run folder while a fix launch is pending, or for stop.md of a /code resume
    whose source changed with no review loop started, else None."""
    tool_input = hook_input.tool_input_of(payload) or {}
    file_path = hook_input.edited_file_path(tool_input)
    if file_path and in_run_folder(file_path):
        resume_reason = resume_review_reason(file_path)
        if resume_reason:
            return resume_reason
        return pending_launch_reason(file_path)
    route_reason = review_fix_route_reason(file_path) if file_path else None
    if route_reason:
        return route_reason
    return DENY_TEXT.format(file_path=file_path or "The Write names no file and")


def main():
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return 0
    stdin_text = sys.stdin.buffer.read().decode("utf-8", "replace")
    payload = json.loads(stdin_text)
    if not isinstance(payload, dict) or payload.get("agent_type") != GATED_AGENT:
        return 0

    try:
        import hook_input
        reason = write_deny_reason(payload, hook_input)
        if reason:
            hook_input.emit_decision("deny", reason)
    except Exception as error:
        # Fail-closed: any crash on the code-fork path blocks the Write and names the gate.
        sys.stderr.write(import_guard.crash_line(GATE_NAME, error, before_read=False))
        return 2
    return 0


if __name__ == "__main__":
    # A crash before the code-fork check (unreadable stdin) exits 0 with a stderr line: fail-open for every caller,
    # since only code-fork is gated and every crash on its own path exits 2 inside main.
    try:
        exit_code = main()
    except Exception as crash:
        sys.stderr.write(f"{GATE_NAME}: could not read the hook input ({crash})\n")
        exit_code = 0
    sys.exit(exit_code)
