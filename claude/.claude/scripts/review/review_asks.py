"""review_asks.py: the ask ids and ask outcome rows of a review packet, for /review (review_fix.py) and /code
(code_step_review.py). A plan-impact ask is not a finding: it gets no id and logs no outcome row."""
import pathlib
import sys
from typing import NamedTuple

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
from script_utils import run_command

ASK_OUTCOMES = ("accepted", "rejected", "modified")


class OutcomeRow(NamedTuple):
    """One ask's outcome row: the finding_id it was logged under, the log helper's exit code and output, and the
    stderr note for an ask logged under a new id (None otherwise)."""
    finding_id: str
    code: int
    output: str
    new_finding_id_note: str | None


def supply_finding_ask_ids(asks, session_id, logger, context, cwd=None):
    """Give each ask that is a finding the id of its ask row, as handback.supply_ask_finding_ids does."""
    # handback is imported where it is used, so code_step can read ASK_OUTCOMES and report a missing handback.py.
    import handback

    finding_asks = [item for item in asks if not handback.is_plan_impact_ask(item)]
    handback.supply_ask_finding_ids(finding_asks, session_id, logger, context, cwd)


def log_ask_outcome(logger, context, item, outcome, decided_by, cwd=None):
    """The OutcomeRow of one ask's outcome, logged with the log helper at `logger`, or None for a plan-impact ask.
    context holds the run fields the ask row and its outcome row share."""
    import handback

    if handback.is_plan_impact_ask(item):
        return None

    finding_id, new_finding_id_note = handback.ask_outcome_finding_id(item)
    code, output = run_command(["bash", str(logger), "kind=finding", f"finding_id={finding_id}",
                                *handback.ask_row_fields(context, item), f"ask_outcome={outcome}",
                                f"ask_decided_by={decided_by}"], cwd)
    return OutcomeRow(finding_id, code, output, new_finding_id_note)
