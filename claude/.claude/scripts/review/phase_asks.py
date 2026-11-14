#!/usr/bin/env python3
"""phase_asks.py: the session's ruling on the finding asks of a /code phase review's packet.

    python3 phase_asks.py list
    python3 phase_asks.py rule <accepted|rejected>:<one-line reason> ...

`code_wait.py review` opens the asks (one `phase-asks-open` row in the hand-back store) when it returns a clean
phase packet (converged, or capped and read as deferred) that holds finding asks. `list` prints them. `rule` takes
one outcome per finding ask, in order, logs each ask's outcome row decided by the session, and stores one
`phase-asks-ruled` row; the commit gate denies a commit in the repo until that row exists; a notes-only commit
still passes. A later review of the repo leaves the asks open: only a newer phase packet with finding asks
replaces them. The reasons stay in the store row: the ledger writer drops free text, so the outcome rows carry
none.
Run from the repo root. Exit 0 when done, 2 when the call is refused (nothing is logged then).
"""
import os
import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import capped_review
import handback
import handback_store
import plan_format
import review_asks
import script_utils
from review_fix_state import ASK_LOGGER

PHASE_ASKS_PATH = pathlib.Path(__file__).resolve()
LIST_COMMAND = f"python3 {PHASE_ASKS_PATH} list"
RULABLE_OUTCOMES = (review_asks.ACCEPTED, review_asks.REJECTED)
SCOPE_PHASE = "phase"


def finding_asks(packet):
    """The packet's asks that are findings; a plan-impact ask is ruled another way."""
    return [item for item in packet["ask"] if not handback.is_plan_impact_ask(item)]


def rule_command(count):
    """The `rule` command line for `count` asks, one placeholder word per ask."""
    words = " ".join(f"'{review_asks.ACCEPTED}|{review_asks.REJECTED}:<one-line reason>'" for _ in range(count))
    return f"python3 {PHASE_ASKS_PATH} rule {words}"


def ask_context(repo, packet, run_info):
    """The run fields the ask rows share. lane and phase come from the /code run's record (run_info), which holds
    none when the run left no record: the rows then carry lane `none` and no phase."""
    context = {"branch": script_utils.current_branch(repo) or "-", "lane": run_info.get("lane", "none"),
               "scope": SCOPE_PHASE, "iter": packet["iter"], "review_round": packet["review_round"]}
    if run_info.get("phase"):
        context["phase"] = run_info["phase"]
    return context


def record_open(session_id, repo, packet, run_info, packet_key):
    """Opens the finding asks of a phase packet for ruling. Returns the lines that tell the session to rule on them,
    empty when the packet is not clean (a blocked or capped loop leaves its asks to the resumed run), holds no
    finding ask, the session has no id, or the repo has no stored hand-back. `packet_key` names the packet (loop folder
    and iteration): a repeat for the same packet adds no row and prints the same lines while the asks are unruled."""
    asks = finding_asks(packet)
    if not session_id or not asks:
        return []
    if capped_review.effective_status(packet, repo) not in handback.CLEAN_STATUSES:
        return []

    stored = handback_store.latest_for_repo(session_id, repo)["handback"]
    if stored is None:
        print(f"phase_asks: no stored hand-back for {repo}, so its {len(asks)} ask(s) are not opened for ruling.",
              file=sys.stderr)
        return []

    context = ask_context(repo, packet, run_info)
    handback_store.record_phase_asks_open(session_id, repo, stored["ts"], asks, context, packet_key)
    if handback_store.unruled_phase_asks(session_id, repo) is None:
        return []
    return [f"{len(asks)} finding ask(s) await your ruling: run `{LIST_COMMAND}`, then `{rule_command(len(asks))}`."]


def session_state():
    """(session id, repo, PhaseAsks or None) of this call."""
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    # The same form the open row's writer and the commit gate use for the store's `repo` key.
    repo = str(script_utils.repo_root(pathlib.Path.cwd()))
    return session_id, repo, handback_store.phase_asks_state(session_id, repo)


def command_list():
    _session_id, repo, state = session_state()
    if state is None:
        print(f"No phase review asks were opened in {repo}. Done.")
        return 0

    asks = state.open_row["asks"]
    print("\n".join(review_asks.numbered_ask_lines(asks)))
    if state.ruled_row is not None:
        print("These asks are already ruled. Done.")
        return 0
    print(f"Rule on all {len(asks)} in order: `{rule_command(len(asks))}`")
    return 0


def read_rulings(words, count):
    """([(outcome, reason)] of the `rule` words, None), or (None, the refusal text)."""
    try:
        outcomes, reasons = review_asks.parse_outcome_words(words, count, RULABLE_OUTCOMES, RULABLE_OUTCOMES)
    except review_asks.OutcomeError as error:
        return None, refusal_text(error, count, len(words))
    return list(zip(outcomes, reasons, strict=True)), None


def refusal_text(error, count, given):
    if error.problem == review_asks.WRONG_COUNT:
        return f"{count} finding ask(s) are open but {given} outcome(s) were given"
    if error.problem == review_asks.UNKNOWN_OUTCOME:
        return f"outcome {error.number} ({error.word!r}) must start with {' or '.join(RULABLE_OUTCOMES)} and a colon"
    return f"outcome {error.number} ({error.word!r}) has no reason after the colon"


def log_outcomes(session_id, repo, asks, rulings, context):
    """Logs each ask's outcome row. Returns one line per row that did not log; the ruling stands either way."""
    review_asks.supply_finding_ask_ids(asks, session_id, ASK_LOGGER, context, repo)
    failures = []
    for number, (item, (outcome, _reason)) in enumerate(zip(asks, rulings, strict=True), 1):
        row = review_asks.log_ask_outcome(ASK_LOGGER, context, item, outcome, plan_format.SESSION_RULING, repo)
        if row.code != 0:
            failures.append(f"ask {number}: {script_utils.one_line(row.output, 160)}")
            continue
        # The id the row was logged under, so the ruled row names the same one.
        item["finding_id"] = row.finding_id
        if row.new_finding_id_note:
            print(f"phase_asks: {row.new_finding_id_note}", file=sys.stderr)
    return failures


def command_rule(words):
    session_id, repo, state = session_state()
    if state is None:
        print("phase_asks: no open phase review asks to rule in this repo. Run `code_wait.py review` for the packet.",
              file=sys.stderr)
        return 2
    if state.ruled_row is not None:
        print("These phase review asks are already ruled; nothing is logged again. Done.")
        return 0

    asks = state.open_row["asks"]
    rulings, refusal = read_rulings(words, len(asks))
    if refusal:
        print(f"phase_asks: {refusal}. Run `{rule_command(len(asks))}`", file=sys.stderr)
        return 2

    failures = log_outcomes(session_id, repo, asks, rulings, state.open_row["context"])
    # One row after the outcome rows: a logger failure must not leave the commit gate closed.
    handback_store.record(session_id, handback_store.PHASE_ASKS_RULED, repo=repo,
                          handback_ts=state.open_row["handback_ts"],
                          rulings=[{"outcome": outcome, "reason": reason, "finding_id": item.get("finding_id")}
                                   for item, (outcome, reason) in zip(asks, rulings, strict=True)])
    for failure in failures:
        print(f"phase_asks: outcome row not logged, {failure}", file=sys.stderr)
    print(f"Ruled {len(asks)} ask(s). List each under `Asks decided` in the phase-complete block. Done.")
    return 0


def main(argv):
    if argv[:1] == ["list"] and len(argv) == 1:
        return command_list()
    if argv[:1] == ["rule"]:
        return command_rule(argv[1:])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
