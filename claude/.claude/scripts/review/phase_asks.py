#!/usr/bin/env python3
"""phase_asks.py: the ruling on the finding asks of a /code phase review's packet.

    python3 phase_asks.py list
    python3 phase_asks.py rule [--by user [{relay_usage}]]
        <accepted|rejected>:<one-line reason> ...

An ask marked `user_only` (a coder's edit to CLAUDE.md, CLAUDE.local.md or AGENTS.md) is refused (exit 2, nothing
logged) unless the call carries `--by user`, which the session uses only to record the user's own ruling. A user
ruling the user gave to another live session is recorded with
`--by user {relay_usage}`
The script needs a real user turn of that session's transcript whose whole text is the quote, typed after the
newest open row of the batch (it comes after every ask it holds, carried ones included), and refuses (exit 2) when
any lookup fails. The relay is stored as an `ask-ruling-relayed` row (who relayed, the quote, the turn's time).
Only a user_only ask is credited to the user; the session rules the rest.

`code_wait.py review` opens the asks (one `phase-asks-open` row in the hand-back store) when it returns a clean
phase packet (converged, or capped and read as deferred) that holds finding asks. `list` prints them. `rule` takes
one outcome per finding ask, in order, logs each ask's outcome row decided by the session, except a user-only ask's
row under `--by user`, which is decided by the user, and stores one `phase-asks-ruled` row that names the open
row it answers, whichever session opened the asks. Each ask ruled `rejected` is also stored as a rejected-ask row (for
the ruling session and each opener), so the next review loop drops a repeat of it. A later review of the repo
leaves the asks open: only a newer phase packet with finding asks replaces them.
The reasons stay in the store row: the ledger writer drops free text, so the outcome rows carry none.
Run from the repo root. Exit 0 when done, 2 when the call is refused (nothing is logged then), 1 when the store is
damaged or cannot be written (the message names the file and line).
"""
import itertools
import os
import pathlib
import shlex
import sys
from typing import NamedTuple

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import capped_review
import handback
import handback_store
import plan_format
import review_asks
import ruling_relay
import script_utils
from approval_asks_store import (
    ApprovalAsksFileError,
    check_approval_paths_readable,
    forget_ruled_approval_paths,
)
from ask_outcome_words import (
    ACCEPTED,
    LIST_COMMAND,
    OUTCOME_PLACEHOLDER,
    REJECTED,
    RELAY_USAGE,
    rule_command,
    rule_instruction,
)
from human_turn_lookup import HumanTurnRefusedError
from review_fix_state import ASK_LOGGER

RULABLE_OUTCOMES = (ACCEPTED, REJECTED)
SCOPE_PHASE = "phase"


def finding_asks(packet):
    """The packet's asks that are findings; a plan-impact ask is ruled another way."""
    return [item for item in packet["ask"] if not handback.is_plan_impact_ask(item)]


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
    finding ask, or the session has no id. `packet_key` names the packet (loop folder
    and iteration): a repeat for the same packet adds no row and prints the same lines while the asks are unruled.
    Raises PhaseAskRowError or OSError (a damaged store, a lock held past its timeout) when the asks cannot be opened:
    the caller fails its step on it."""
    asks = finding_asks(packet)
    if not session_id or not asks:
        return []
    if capped_review.effective_status(packet, repo) not in handback.CLEAN_STATUSES:
        return []

    context = ask_context(repo, packet, run_info)
    handback_store.record_phase_asks_open(session_id, repo, asks, context, packet_key)
    unruled = handback_store.unruled_phase_asks(repo)
    if unruled is None:
        return []
    open_asks = unruled["asks"]
    open_count = len(open_asks)
    return [f"{open_count} finding ask(s) await your ruling: run `{LIST_COMMAND}`, then "
            f"{rule_instruction(open_asks)}."]


def session_state():
    """(session id, repo, PhaseAsks or None) of this call. The asks are the repo's, whichever session opened them.
    Raises what handback_store.read_phase_ask_rows raises."""
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    # The same form the open row's writer uses for the store's `repo` key.
    repo_top = script_utils.repo_root(pathlib.Path.cwd())
    if repo_top is None:
        return session_id, None, None
    repo = str(repo_top)
    return session_id, repo, handback_store.phase_asks_state(repo)


def refuse_outside_repo():
    print(f"phase_asks: run from the repo root; {pathlib.Path.cwd()} is not in a work tree.", file=sys.stderr)
    return 2


def command_list():
    _session_id, repo, state = session_state()
    if repo is None:
        return refuse_outside_repo()
    if state is None:
        print(f"No phase review asks were opened in {repo}. Done.")
        return 0

    asks = state.open_row["asks"]
    print("\n".join(review_asks.numbered_ask_lines(asks)))
    if state.ruled_row is not None:
        print("These asks are already ruled. Done.")
        return 0
    print(f"Rule on all {len(asks)} in order: {rule_instruction(asks)}")
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
    if error.problem == review_asks.UNKNOWN_OUTCOME and error.word == OUTCOME_PLACEHOLDER:
        return (f"outcome {error.number} is the printed placeholder: replace it with "
                f"{' or '.join(RULABLE_OUTCOMES)}, a colon and a reason")
    if error.problem == review_asks.UNKNOWN_OUTCOME:
        return f"outcome {error.number} ({error.word!r}) must start with {' or '.join(RULABLE_OUTCOMES)} and a colon"
    return f"outcome {error.number} ({error.word!r}) has no reason after the colon"


def supply_ids_by_context(session_id, repo, asks, contexts, stall):
    """Gives each ask its finding id, one batch per run of asks that share a context."""
    for context, pairs in itertools.groupby(zip(asks, contexts, strict=True), key=lambda pair: pair[1]):
        run_asks = [item for item, _context in pairs]
        review_asks.supply_finding_ask_ids(run_asks, session_id, ASK_LOGGER, context, repo, stall)


class RuledCall(NamedTuple):
    """The words of a `rule` call: who rules, the outcome words, and the relay request (None for no relay)."""
    ruler: str
    outcome_words: list
    relay: ruling_relay.RelayRequest | None


def split_ruler(words):
    """(RuledCall, None), or (None, the refusal text). `--by user` marks the ruling as the user's; no `--by` is the
    session's. `--relayed-by` and `--quote` go with `--by user`."""
    outcome_words, ruler = script_utils.pop_option(words, "--by")
    if ruler is None:
        ruler = plan_format.SESSION_RULING
    elif ruler != plan_format.USER_RULING:
        return None, f"--by takes only `{plan_format.USER_RULING}`, not {ruler!r}"
    try:
        outcome_words, relay = ruling_relay.pop_relay_options(outcome_words)
        ruling_relay.refuse_relay_without_user(relay, ruler)
    except ruling_relay.RelayRefusedError as error:
        return None, ruling_relay.relay_refusal_line(error)
    return RuledCall(ruler, outcome_words, relay), None


def verified_phase_relay(call, asks, filed_at):
    """(RelayedRuling or None, None), or (None, the refusal text). The relay of `call` is verified against the
    relaying session's transcript for a turn after `filed_at`; a call with no relay gives (None, None)."""
    if call.relay is None:
        return None, None
    try:
        ruling_relay.refuse_relay_without_user_only(asks)
        # The bound is the newest open row's time, which comes after every ask it holds, carried ones included: a
        # turn typed before a carried batch's newest packet is refused.
        return ruling_relay.verify_relay(call.relay, filed_at), None
    except HumanTurnRefusedError as error:
        return None, ruling_relay.relay_refusal_line(error)


def ruler_of_call(words, asks):
    """(RuledCall, None), or (None, the refusal text) when the `--by` word is unknown or a session rules on a user-only
    ask."""
    call, refusal = split_ruler(words)
    if refusal:
        return None, refusal
    user_command = f"rule --by {plan_format.USER_RULING} ..."
    refusal = review_asks.user_only_refusal(asks, call.ruler, user_command)
    if refusal:
        return None, refusal
    return call, None


class OutcomeLog(NamedTuple):
    failures: list[str]  # one line per row that did not log
    logged_asks: list[dict]  # the asks whose row logged


def log_outcomes(session_id, repo, asks, rulings, contexts, ruler=plan_format.SESSION_RULING):
    """Logs each ask's outcome row under the ask's own context (`contexts` is one per ask), one per ask. `ruler` is
    the call's: the row of a user-only ask is decided by the user under `--by user`, every other row by the session.
    Returns an OutcomeLog: a line per row that did not log, and the asks whose row did; the ruling stands either
    way. After one log helper call times out, no other call is made: a hung ledger costs one timeout, and each
    unlogged row still gets its line."""
    stall = handback.LoggerStall()
    supply_ids_by_context(session_id, repo, asks, contexts, stall)
    failures = []
    logged_asks = []
    for number, (item, (outcome, _reason)) in enumerate(zip(asks, rulings, strict=True), 1):
        context = contexts[number - 1]
        ask_ruler = review_asks.ruler_of_ask(item, ruler)
        row = review_asks.log_ask_outcome(ASK_LOGGER, context, item, outcome, ask_ruler, repo, stall)
        if row.code != 0:
            failures.append(f"ask {number}: {script_utils.one_line(row.output, 160)}. "
                            f"Log it later with `{shlex.join(row.command)}`")
            continue
        # The id the row was logged under, so the ruled row names the same one.
        item["finding_id"] = row.finding_id
        logged_asks.append(item)
        if row.new_finding_id_note:
            print(f"phase_asks: {row.new_finding_id_note}", file=sys.stderr)
    return OutcomeLog(failures, logged_asks)


def command_rule(words):
    """The ruling, from the read of the open asks to the last ruled row, under the store's phase-asks lock: a second
    `rule` started at the same time in the repo waits, then finds the asks ruled. A lock held past the timeout raises
    OSError and nothing is logged."""
    repo_top = script_utils.repo_root(pathlib.Path.cwd())
    if repo_top is None:
        return refuse_outside_repo()
    with handback_store.phase_asks_lock(str(repo_top)):
        return rule_open_asks(words)


def rule_open_asks(words):
    session_id, repo, state = session_state()
    if repo is None:
        return refuse_outside_repo()
    if state is None:
        print("phase_asks: no open phase review asks to rule in this repo. Run `code_wait.py review` for the packet.",
              file=sys.stderr)
        return 2
    if state.ruled_row is not None:
        print("These phase review asks are already ruled; nothing is logged again. Done.")
        return 0

    if not session_id:
        print("phase_asks: CLAUDE_CODE_SESSION_ID is not set; the ruling's outcome rows are logged under it. "
              "Nothing was logged.", file=sys.stderr)
        return 2

    asks = state.open_row["asks"]
    call, refusal = ruler_of_call(words, asks)
    if refusal:
        print(f"phase_asks: {refusal}. Nothing was logged.", file=sys.stderr)
        return 2
    ruler = call.ruler
    relayed, refusal = verified_phase_relay(call, asks, state.open_row["ts"])
    if refusal:
        print(f"phase_asks: {refusal}. Nothing was logged.", file=sys.stderr)
        return 2
    rulings, refusal = read_rulings(call.outcome_words, len(asks))
    if refusal:
        print(f"phase_asks: {refusal}. Run `{rule_command(len(asks), by_user=ruler == plan_format.USER_RULING)}`",
              file=sys.stderr)
        return 2

    # A ruled row goes to the file of each session whose open row it answers (the latest open row, and the older ones
    # its asks were carried from): prune_stale deletes a file by its own age, and a ruling kept in another file could
    # vanish while an open row stays.
    answered_rows = handback_store.unruled_open_rows(repo)
    # The rejected-ask rows go to the ruling session and to each session that opened the asks, once each.
    store_sessions = list(dict.fromkeys([session_id, *(open_row["session_id"] for open_row in answered_rows)]))
    for store_session in store_sessions:
        store_file = handback_store.session_file(store_session)
        if not script_utils.can_append(store_file):
            # Checked before any row is written or outcome row logged: a rerun would log them all again.
            print(f"phase_asks: cannot write the ruling: {store_file} or its folder is not writable. Nothing was "
                  "logged.", file=sys.stderr)
            return 1

    rows_repo = handback_store.ruled_rows_repo(repo)
    outcomes = [outcome for outcome, _reason in rulings]
    # Checked before any row is written: a damaged file must stop the ruling with nothing logged.
    try:
        check_approval_paths_readable(rows_repo, asks)
    except ApprovalAsksFileError as error:
        print(f"phase_asks: {error}. Nothing was logged.", file=sys.stderr)
        return 1

    # Before the outcome rows: a hung or failed logger must not lose them. A rerun adds none (the store skips a text
    # already rejected). The key is the one the review loop reads them under.
    review_asks.record_rejected_asks(store_sessions, rows_repo, asks, outcomes)
    # A ruled approval ask leaves the saved paths, so a resumed review loop does not file it again.
    forget_ruled_approval_paths(rows_repo, asks)

    contexts = state.open_row["contexts"]
    outcome_log = log_outcomes(session_id, repo, asks, rulings, contexts, ruler)
    failures = outcome_log.failures
    if relayed is not None:
        ruling_relay.record_relay(session_id, rows_repo, relayed, outcome_log.logged_asks)
    # One row per answered open row, after the outcome rows: a logger failure must not leave the asks open.
    # A row names the open row it answers, so an open row written while the outcomes were logging stays open.
    ruled_rulings = [{"outcome": outcome, "reason": reason, "finding_id": item.get("finding_id")}
                     for item, (outcome, reason) in zip(asks, rulings, strict=True)]
    for open_row in answered_rows:
        handback_store.record(open_row["session_id"], handback_store.PHASE_ASKS_RULED, repo=repo,
                              **{handback_store.RULED_OPEN_TS_KEY: open_row["ts"],
                                 handback_store.RULED_BY_KEY: session_id},
                              rulings=ruled_rulings)
    for failure in failures:
        print(f"phase_asks: outcome row not logged, {failure}", file=sys.stderr)
    print(f"Ruled {len(asks)} ask(s). List each under `Asks decided` in the phase-complete block. Done.")
    return 0


def main(argv):
    try:
        if argv[:1] == ["list"] and len(argv) == 1:
            return command_list()
        if argv[:1] == ["rule"]:
            return command_rule(argv[1:])
    except handback_store.PhaseAskRowError as error:
        print(f"phase_asks: damaged phase-asks row in the hand-back store, {error}. Fix or delete that line.",
              file=sys.stderr)
        return 1
    except OSError as error:
        print(f"phase_asks: cannot read or write the hand-back store: {error}", file=sys.stderr)
        return 1
    print(__doc__.format(relay_usage=RELAY_USAGE), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
