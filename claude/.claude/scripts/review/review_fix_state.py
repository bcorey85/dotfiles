"""review_fix_state.py: what every review_fix.py verb shares: the saved state under <git dir>/review-fix, the
usage error, the ACTION and user-text printers, and the ask logger."""
import argparse
import json
import os
import pathlib
import sys

import handback_store
import script_utils
from ask_outcome_words import USER_ONLY_KEY
from review_fix_names import (
    ASK_FINDINGS_NAME,
    ASKS_DECIDED_BY_KEY,
    CORRECT_OPEN_KEY,
    FILED_AT_KEY,
    PENDING_LAUNCH_KEY,
    PLAN_IMPACT_FILED_AT_KEY,
    RESTORED_INDEXES_KEY,
    REVIEW_FIX_FOLDER,
    STATE_FILE_NAME,
)

CLAUDE_DIR = pathlib.Path(os.environ.get("REVIEW_FIX_CLAUDE_DIR", pathlib.Path(__file__).resolve().parents[2]))
ASK_LOGGER = CLAUDE_DIR / "skills/review/log-review-finding"
REVIEW_FIX_COMMAND = "python3 ~/.claude/scripts/review/review_fix.py"
# The review fork matches this line to decide whether to dispatch the coder.
ADD_DEVIATIONS_LINE = "Add these lines under ## Plan Deviations in the plan, and show the user:"
DEFER_LINE_PREFIX = "plan_impact: RESOLVED: deferred to phase end"
DEFER_LINE = f"{DEFER_LINE_PREFIX} by the session, <date>: <summary>"

DEFER_COMMAND = f"{REVIEW_FIX_COMMAND} defer"


def defer_instruction(handoff_file):
    """The sentence that tells the session to defer held plan impacts: write the one-line deferral into the handoff
    file, then run the defer command on it."""
    return (f"Set `plan_impact` in {handoff_file} to the one line `{DEFER_LINE.removeprefix('plan_impact: ')}` and "
            f"run `{DEFER_COMMAND} {handoff_file}`.")


# State keys a repeat of the same packet keeps from the previous state.
SAME_RUN_STATE_KEYS = (
    "stage",
    "asks",
    "jumped",
    "aikido_posted",
    "escapes_logged",
    "asks_logged",
    "asks_redispatched",
    "asks_launch_line",
    ASKS_DECIDED_BY_KEY,
    "ask_outcomes",
    "ask_notes",
    CORRECT_OPEN_KEY,
    RESTORED_INDEXES_KEY,
    "last_asks_launch_line",
    "last_ask_outcomes",
    "last_ask_notes",
    "asks_deviations_printed",
    "asks_rejections_recorded",
    "asks_relay_recorded",
    "plan_impact",
    "plan_impact_held",
    "plan_impact_applied",
    "plan_impact_adopt_settles",
    PLAN_IMPACT_FILED_AT_KEY,
    "carried_findings",
    "waiting_packets",
    "relaunch_args",
)


class UsageError(Exception):
    pass


def argument_parser(name):
    parser = argparse.ArgumentParser(prog=f"review_fix.py {name}", add_help=False)
    parser.error = lambda message: (_ for _ in ()).throw(UsageError(message))
    return parser


def review_fix_dir():
    found = script_utils.git_path(".", REVIEW_FIX_FOLDER)
    if found is None:
        raise UsageError("not inside a git repo")
    return found


def review_fix_state_file():
    return review_fix_dir() / STATE_FILE_NAME


def clear_asks_launch_pending(findings_file):
    """Clears the pending fix-run flag when findings_file is the asks-done findings file. The fix state sits beside
    that file, so the launch's --repo plays no part. Any other file, a missing state, or a state that is not
    readable JSON is left as it is."""
    findings_path = pathlib.Path(findings_file).resolve()
    run_dir = findings_path.parent
    if findings_path.name != ASK_FINDINGS_NAME or run_dir.name != REVIEW_FIX_FOLDER:
        return
    state_file = run_dir / STATE_FILE_NAME
    if not state_file.exists():
        return
    state = read_state(state_file)
    if state is None:
        print(f"review_fix: {state_file} is not readable JSON; the pending fix-run flag was not cleared.",
              file=sys.stderr)
        return
    if PENDING_LAUNCH_KEY not in state:
        return
    del state[PENDING_LAUNCH_KEY]
    save_fix_state(state, state_file)


def read_state(state_file=None):
    """The saved state, or None when there is none or it is unreadable. state_file defaults to this repo's. Each
    user-only ask saved with no filed time (current and waiting), and a plan impact saved with none, is stamped with
    the file's modification time, read
    before any caller saves: the time is no earlier than the save that filed the ask, so a relayed quote typed before it
    is refused, and the stamp keeps a later save from moving it."""
    path = state_file or review_fix_state_file()
    if not path.exists():
        return None
    state_written_at = path.stat().st_mtime
    try:
        state = json.loads(path.read_text())
    except ValueError:
        return None
    stamp_legacy_filed_at(state.get("asks") or [], state_written_at)
    if state.get("plan_impact"):
        state.setdefault(PLAN_IMPACT_FILED_AT_KEY, state_written_at)
    for kept in state.get("waiting_packets") or []:
        stamp_legacy_filed_at(kept.get("asks") or [], state_written_at)
    return state


def stamp_legacy_filed_at(asks, state_written_at):
    """Stamps each user-only ask in `asks` that has no filed time with `state_written_at`."""
    for item in asks:
        if item.get(USER_ONLY_KEY):
            item.setdefault(FILED_AT_KEY, state_written_at)


def load_fix_state():
    state = read_state()
    if state is not None:
        return state
    raise missing_fix_state_error()


def missing_fix_state_error():
    """The UsageError that says why read_state found no state: the file is unreadable, or no packet was processed."""
    path = review_fix_state_file()
    if path.exists():
        return UsageError(f"{path} is not readable JSON")
    return UsageError(f"no packet was processed in {path.parent} (the state is kept per repo, and this call ran in "
                      f"{pathlib.Path.cwd()}). If `packet` ran in another repo, run this call there; if it ran "
                      "in none, run `packet` first.")


def save_fix_state(state, state_file=None):
    path = state_file or review_fix_state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    script_utils.write_text_atomically(path, json.dumps(state, indent=1))


def has_unanswered_asks(packet_state):
    asks = packet_state.get("asks") or []
    logged = packet_state.get("asks_logged", [])
    return any(index not in logged for index in range(len(asks)))


def record_packet_asks_logged(packet_id):
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not session_id:
        return
    repo = script_utils.work_tree_top(".")
    handback_store.record_asks_logged(session_id, packet_id, repo)


def repo_that_logged_packet_asks(packet_id):
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not session_id:
        return None
    return handback_store.repo_that_logged_the_asks(session_id, packet_id)


def print_user_block(text):
    print("-----BEGIN USER TEXT (paste verbatim)-----")
    print(text)
    print("-----END USER TEXT-----")


def print_action(action, *lines):
    print(f"ACTION: {action}")
    for line in lines:
        print(line)
