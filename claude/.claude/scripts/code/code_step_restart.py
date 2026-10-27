"""code_step_restart.py: when `start` may replace an open run, and how it drops one.

Imports run one way: code_step_core, code_step_restart, code_step."""
from code_step_core import is_run_open, session_pin, state_dir


def reopens_stopped_run(previous):
    # A run that stopped on the coder's report, in the session that now runs `start` again: the session has seen the
    # report and starts over on its own word.
    pinned = session_pin()
    return (previous.get("stage") == "stopped" and not previous.get("stopReason")
            and bool(previous.get("resumableCoderId")) and pinned is not None and previous.get("sessionId") == pinned)


def drop_open_run(repo_dir, previous):
    # The open run leaves no state behind: a later stop of this start leaves nothing open for the next `start` to
    # refuse. The caller keeps `previous` in memory for the baseline of a restarted phase.
    if not is_run_open(previous):
        return

    (state_dir(repo_dir) / "state.json").unlink(missing_ok=True)
