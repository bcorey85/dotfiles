"""held_asks.py: the `held` outcome of an asks-done call. A session may hold a user-only ask for the user's own
`--by user` call: this module refuses a misplaced `held` and splits a packet's asks into the plain ones and the held
ones."""
from typing import NamedTuple

import plan_format
import review_asks
from ask_outcome_words import HELD, USER_ONLY_KEY
from review_asks import MODIFIED
from review_fix_state import UsageError


def refuse_misplaced_held(target, outcomes, decided_by):
    """Refuses (nothing is logged) `held` in a `--by user` call, on an ask that is not user-only, on every ask of
    the packet (a call that holds all of them rules nothing), and on a retry of a packet whose outcomes are already
    logged (an ask the user ruled cannot move to the held packet)."""
    asks = target["asks"]
    if HELD in outcomes and target.get("ask_outcomes") is not None:
        raise UsageError("asks-done is a retry: a retry gives the outcomes already logged, never `held`. "
                         "Nothing was logged.")
    problems = []
    for number, (item, outcome) in enumerate(zip(asks, outcomes, strict=True), 1):
        if outcome != HELD:
            continue
        if decided_by == plan_format.USER_RULING:
            problems.append(f"ask {number}: {HELD} is for a session call; a `--by user` call rules every ask")
        elif not item.get(USER_ONLY_KEY):
            problems.append(f"ask {number}: {HELD} is only for a user_only ask; give this one "
                            f"{review_asks.PLAIN_OUTCOMES_TEXT} or '{MODIFIED}:<the change>'")
    if problems:
        raise UsageError("\n".join(problems) + "\nNothing was logged.")
    if all(outcome == HELD for outcome in outcomes):
        raise UsageError(f"every ask is {HELD}: the call would rule nothing. Leave the packet for the user's "
                         "`--by user` call. Nothing was logged.")


class HeldSplit(NamedTuple):
    """The asks of a packet split by the call's outcomes: the plain asks with their outcomes and notes, and the
    held asks."""
    plain_asks: list
    plain_outcomes: list
    plain_notes: list
    held_asks: list


def split_held(asks, outcomes, notes):
    """The HeldSplit of the asks. Changes nothing."""
    split = HeldSplit([], [], [], [])
    for item, outcome, note in zip(asks, outcomes, notes, strict=True):
        if outcome == HELD:
            split.held_asks.append(item)
            continue
        split.plain_asks.append(item)
        split.plain_outcomes.append(outcome)
        split.plain_notes.append(note)
    return split
