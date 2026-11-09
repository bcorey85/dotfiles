"""review_fix_state.py: what every review_fix.py verb shares: the saved state under <git dir>/review-fix, the
usage error, the ACTION and user-text printers, and the ask logger."""
import argparse
import json
import os
import pathlib

import handback_store
import script_utils

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
    found = script_utils.git_path(".", "review-fix")
    if found is None:
        raise UsageError("not inside a git repo")
    return found


def review_fix_state_file():
    return review_fix_dir() / "state.json"


def read_state():
    """The saved state, or None when there is none or it is unreadable."""
    path = review_fix_state_file()
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


def save_fix_state(state):
    path = review_fix_state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    script_utils.write_text_atomically(path, json.dumps(state, indent=1))


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
