"""The ask outcome words and the `phase_asks.py` command lines the commit gate prints. No imports beyond the standard
library: it keeps the commit gate from importing `phase_asks`."""
import pathlib

ACCEPTED = "accepted"
REJECTED = "rejected"
PHASE_ASKS_PATH = pathlib.Path(__file__).resolve().parent.parent / "review" / "phase_asks.py"
LIST_COMMAND = f"python3 {PHASE_ASKS_PATH} list"
# The word `rule_command` prints for each ask. A session that types it as it stands is refused with a pointer to it.
OUTCOME_PLACEHOLDER = f"{ACCEPTED}|{REJECTED}:<one-line reason>"


def rule_command(count):
    """The `rule` command line for `count` asks, one placeholder word per ask."""
    words = " ".join(f"'{OUTCOME_PLACEHOLDER}'" for _ in range(count))
    return f"python3 {PHASE_ASKS_PATH} rule {words}"
