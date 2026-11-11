"""review_fix_state.py: what every review_fix.py verb shares: the saved state under <git dir>/review-fix, the
usage error, the ACTION and user-text printers, and the ask logger."""
import argparse
import json
import os
import pathlib
import sys

import handback_store
import script_utils
from review_fix_names import (
    ASK_FINDINGS_NAME,
    PENDING_LAUNCH_KEY,
    REVIEW_FIX_FOLDER,
    STATE_FILE_NAME,
)
from review_fix_names import (
    CORRECT_OPEN_KEY as CORRECT_OPEN_KEY,
)

CLAUDE_DIR = pathlib.Path(os.environ.get("REVIEW_FIX_CLAUDE_DIR", pathlib.Path(__file__).resolve().parents[2]))
ASK_LOGGER = CLAUDE_DIR / "skills/review/log-review-finding"
REVIEW_FIX_COMMAND = "python3 ~/.claude/scripts/review/review_fix.py"
# The review fork matches this line to decide whether to dispatch the coder.
ADD_DEVIATIONS_LINE = "Add these lines under ## Plan Deviations in the plan, and show the user:"


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
    """The saved state, or None when there is none or it is unreadable. state_file defaults to this repo's."""
    path = state_file or review_fix_state_file()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except ValueError:
        return None


def load_fix_state():
    state = read_state()
    if state is not None:
        return state
    path = review_fix_state_file()
    if path.exists():
        raise UsageError(f"{path} is not readable JSON")
    raise UsageError(f"no packet was processed in {path.parent} (the state is kept per repo, and this call ran in "
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
