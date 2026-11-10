#!/usr/bin/env python3
"""PreToolUse hook on Write: the code-fork agent writes only files inside a run folder.

code-fork runs the /code, /review and /fix steps. A coder makes every repo edit; the fork writes only its own
handoff and stop files in the run folder, `git rev-parse --git-path code-phase`: a `code-phase` directory whose
parent is a git directory (it holds a HEAD file). A shell heredoc cannot carry that text, because the safety gate
reads a heredoc's body as command text. Any other agent, and the main session, passes untouched.

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
ERROR_TEXT = "fork_write_scope: could not judge the Write ({error}) - denied."


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


def load_hook_input():
    lib_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")
    sys.path[:0] = [lib_dir]
    import hook_input
    return hook_input


def out_of_folder_reason(payload, hook_input):
    """The deny text for a code-fork Write outside a run folder, else None."""
    tool_input = hook_input.tool_input_of(payload) or {}
    file_path = hook_input.edited_file_path(tool_input)
    if file_path and in_run_folder(file_path):
        return None
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
        reason = out_of_folder_reason(payload, hook_input)
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
