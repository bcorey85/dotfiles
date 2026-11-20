"""The ask outcome words and the `phase_asks.py` command lines the commit gate prints. No imports beyond the standard
library: it keeps the commit gate from importing `phase_asks`."""
import pathlib

ACCEPTED = "accepted"
# The ask entry key that marks an ask only the user rules (a coder's edit to an approval-only file).
USER_ONLY_KEY = "user_only"
# The mark a listing prints in front of or after a `user_only` ask.
USER_ONLY_MARK = "[user only]"
REJECTED = "rejected"
# A review-fix outcome: the ruler accepted the ask and its change is already in the tree. It logs as ACCEPTED and
# writes no finding.
APPLIED = "applied"
# A review-fix outcome valid only on a user-only ask in a session call: the ask is not ruled and waits for the user's
# own `--by user` call. It logs nothing.
HELD = "held"
PHASE_ASKS_PATH = pathlib.Path(__file__).resolve().parent.parent / "review" / "phase_asks.py"
LIST_COMMAND = f"python3 {PHASE_ASKS_PATH} list"
# The word `rule_command` prints for each ask. A session that types it as it stands is refused with a pointer to it.
OUTCOME_PLACEHOLDER = f"{ACCEPTED}|{REJECTED}:<one-line reason>"


# The options that relay a user ruling given to another session, as the ruling parsers accept them and as the
# refusals and usage lines print them.
RELAYED_BY_FLAG = "--relayed-by"
QUOTE_FLAG = "--quote"
RELAY_USAGE = f'{RELAYED_BY_FLAG} <session name> {QUOTE_FLAG} "<the user\'s exact words>"'


def rule_command(count, by_user=False):
    """The `rule` command line for `count` asks, one placeholder word per ask. `by_user` adds `--by user`, the form
    that records the user's own ruling."""
    words = " ".join(f"'{OUTCOME_PLACEHOLDER}'" for _ in range(count))
    by_flag = "--by user " if by_user else ""
    return f"python3 {PHASE_ASKS_PATH} rule {by_flag}{words}"


def user_only_numbers(asks):
    """The 1-based numbers of the asks marked `user_only`."""
    return [number for number, item in enumerate(asks, 1) if item.get(USER_ONLY_KEY)]


def rule_instruction(asks):
    """The text that says which `rule` line records the ruling on `asks`: the session's own line, or, when an ask is
    marked `user_only`, a hand-off to the user and the `--by user` line."""
    numbers = user_only_numbers(asks)
    if not numbers:
        return f"`{rule_command(len(asks))}`"
    listed = ", ".join(str(number) for number in numbers)
    return (f"hand ask(s) {listed} to the user (a fix coder edited an approval-only file) and record the user's "
            f"outcomes with `{rule_command(len(asks), by_user=True)}`")
