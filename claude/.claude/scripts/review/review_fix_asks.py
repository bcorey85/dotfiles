"""review_fix_asks.py: `review_fix.py asks-done`. It logs one outcome row per ask, once; `--correct` logs one more row
for each corrected ask while the printed fix run has not launched. When the user accepted or modified an ask, it
writes those asks to a findings file and prints the fix run that applies them: the first run's launch flags plus
`--fix`, `--iter`, `--fix-rounds`, `--post-cap-passes` and `--detach`, so the loop's fix coder makes the change, a
review round covers it, and the converged hand-back earns review credit."""
import os
import shlex
import sys
from typing import NamedTuple

import approval_restore
import handback_store
import plan_format
import review_asks
import review_launch
import ruling_relay
import script_utils
from approval_asks_store import (
    ApprovalAsksFileError,
    check_approval_paths_readable,
    forget_ruled_approval_paths,
    is_approval_ask,
    read_held_changes,
    user_only_changes,
    write_held_changes,
)
from ask_outcome_words import HELD, USER_ONLY_KEY
from handback import PLAN_IMPACT_STATUS, is_plan_impact_ask
from held_asks import refuse_misplaced_held, split_held
from human_turn_lookup import HumanTurnRefusedError
from review_asks import (
    ACCEPT_MEANS,
    ACCEPTED,
    APPLIED,
    APPLIED_MEANS,
    ASK_OUTCOMES,
    HELD_MEANS,
    MODIFIED,
    REJECT_MEANS,
    REJECTED,
    SESSION_CALL_OUTCOMES,
    USER_RULED_KEY,
    rejected_ask_text,
)
from review_fix_names import PACKET_IDENTITY_KEYS, RUN_FOLDER_FINDINGS_NAME
from review_fix_state import (
    ADD_DEVIATIONS_LINE,
    ASK_FINDINGS_NAME,
    ASK_LOGGER,
    ASKS_DECIDED_BY_KEY,
    CORRECT_OPEN_KEY,
    PENDING_LAUNCH_KEY,
    REVIEW_FIX_COMMAND,
    UsageError,
    has_unanswered_asks,
    load_fix_state,
    print_action,
    record_packet_asks_logged,
    review_fix_dir,
    save_fix_state,
)
from review_loop_findings import criteria_covered, plan_item_criteria_ids
from ruled_change_text import SESSION_CLAUSE, UNNAMED_CLAUSE, USER_CLAUSE, changed_text
from saved_handback import dispatched_repo, session_repo
from script_utils import one_line, split_location

NEW_FINDING_ID = "new-finding-id"
CORRECT_FLAG = "--correct"
LAUNCH_COMMAND = f"{REVIEW_FIX_COMMAND} launch"
NO_LAUNCH_RECORD_ACTION = "launch-fix-run"
STALE_RUN_FOLDER_FINDINGS_REMOVED = (
    f"An older {RUN_FOLDER_FINDINGS_NAME} in the run folder was removed; write a new one only if findings were "
    "deferred to this run.")
PRINTED_RUN_LINE = "The first asks-done printed this fix run; run it now unless it already ran."


def read_outcomes(argv, asks, allow_held=False):
    """(the outcome word of each ask, the note after `:` of each, "" when none). A modified ask needs its note: the
    note is the ruler's change. `allow_held` lets the first asks-done call give `held`; every other caller refuses it
    as an unknown word."""
    allowed = SESSION_CALL_OUTCOMES if allow_held else ASK_OUTCOMES
    try:
        return review_asks.parse_outcome_words(argv, len(asks), allowed, (MODIFIED,))
    except review_asks.OutcomeError as error:
        if error.problem == review_asks.WRONG_COUNT:
            raise UsageError(f"{len(asks)} ask(s) waiting but {len(argv)} outcome(s) given") from error
        if error.problem == review_asks.UNKNOWN_OUTCOME:
            held_text = f"; {HELD}: {HELD_MEANS}" if allow_held else ""
            raise UsageError(
                f"outcome {error.word!r} is not one of {'|'.join(allowed)}. {ACCEPTED}: {ACCEPT_MEANS}; "
                f"{REJECTED}: {REJECT_MEANS} (the outcome for a 'leave it' or 'accept the gap' "
                f"option); {APPLIED}: {APPLIED_MEANS}; "
                f"{MODIFIED}:<change>: make that change instead{held_text}") from error
        raise UsageError(f"outcome {error.number} is modified with no note; "
                         f"write '{MODIFIED}:<the change>' quoted as one shell word") from error


def outcome_failure_line(item, outcome_row):
    """The failure line of an ask outcome row that did not log."""
    path, line = split_location(item.get("file_line") or "-")
    return f"{path}:{line}: {one_line(outcome_row.output, 160)}"


class LoggedOutcomes(NamedTuple):
    """What one asks-done call logged: the ask counts (plan-impact asks skipped, outcomes logged under a new
    finding_id), the failure lines, and the indexes of the asks this call added to asks_logged."""
    ask_counts: dict
    failures: list
    new_indexes: list


def log_fix_ask_outcomes(state, asks, outcomes, decided_by):
    """The LoggedOutcomes of this call. An ask that is logged or skipped joins asks_logged and is never tried
    again."""
    logged = state.setdefault("asks_logged", [])
    ask_counts = {PLAN_IMPACT_STATUS: 0, NEW_FINDING_ID: 0}
    failures = []
    new_indexes = []
    for index, (item, outcome) in enumerate(zip(asks, outcomes, strict=True)):
        if index in logged:
            continue

        outcome_row = review_asks.log_ask_outcome(ASK_LOGGER, state, item, outcome, decided_by)
        if outcome_row is None:
            ask_counts[PLAN_IMPACT_STATUS] += 1
            logged.append(index)
            new_indexes.append(index)
            continue
        if outcome_row.code == 0:
            logged.append(index)
            new_indexes.append(index)
            # A minted id is kept so a later `--correct` row supersedes this one.
            item["finding_id"] = outcome_row.finding_id
            if outcome_row.new_finding_id_note:
                print(f"review-fix: {outcome_row.new_finding_id_note}", file=sys.stderr)
                ask_counts[NEW_FINDING_ID] += 1
            continue
        failures.append(outcome_failure_line(item, outcome_row))
    return LoggedOutcomes(ask_counts, failures, new_indexes)


def waiting_ask_packets(state):
    """The packets that hold unanswered asks: the current one, then the kept ones, oldest first."""
    waiting = []
    # A stage-asks state with every ask already logged is a retry that asks-done must still accept.
    if has_unanswered_asks(state) or (state.get("stage") == "asks" and state.get("asks")):
        waiting.append(state)
    waiting += [kept for kept in state.get("waiting_packets") or [] if has_unanswered_asks(kept)]
    return waiting


def waiting_packet_lines(waiting):
    lines = []
    for packet_state in waiting:
        asks = packet_state["asks"]
        first = asks[0]
        lines.append(f"- {packet_state['packet_id']}: {len(asks)} ask(s); first: "
                     f"{first.get('file_line') or 'no file:line'} {one_line(first['question'], 120)}")
    return lines


def choose_asks_packet(waiting, packet_id):
    """The one waiting packet the outcomes belong to. Refuses when several wait and none is named."""
    if packet_id is None and len(waiting) == 1:
        return waiting[0]
    if packet_id is None:
        raise UsageError("more than one packet holds unanswered asks. Rerun asks-done with --packet <packet_id> for "
                         "the one you answer:\n" + "\n".join(waiting_packet_lines(waiting)))
    for packet_state in waiting:
        if packet_state["packet_id"] == packet_id:
            return packet_state
    raise UsageError(f"--packet {packet_id!r} is not a packet with unanswered asks. Waiting:\n"
                     + "\n".join(waiting_packet_lines(waiting)))


class AsksDoneOptions(NamedTuple):
    """The parsed words of an asks-done call."""
    outcome_words: list
    decided_by: str
    packet_id: str | None
    correct: bool
    relay: ruling_relay.RelayRequest | None


def asks_done_options(argv):
    """The AsksDoneOptions of an asks-done call."""
    outcome_words, decided_by = script_utils.pop_option(argv, "--by")
    if decided_by is None:
        raise UsageError("asks-done needs --by: `--by user` when the user gave the answer, `--by session` when "
                         "the session ruled on the asks itself.")
    if not plan_format.is_ruling_by(decided_by):
        raise UsageError(f"asks-done --by needs user or session, not {decided_by!r}")
    try:
        outcome_words, relay = ruling_relay.pop_relay_options(outcome_words)
        ruling_relay.refuse_relay_without_user(relay, decided_by)
    except ruling_relay.RelayRefusedError as error:
        raise UsageError(f"{ruling_relay.relay_refusal_line(error)}. Nothing was logged.") from error

    outcome_words, packet_id = script_utils.pop_option(outcome_words, "--packet")
    if packet_id == "":
        raise UsageError("asks-done --packet needs a packet_id")
    correct = CORRECT_FLAG in outcome_words
    outcome_words = [word for word in outcome_words if word != CORRECT_FLAG]
    return AsksDoneOptions(outcome_words, decided_by, packet_id, correct, relay)


def verified_fix_relay(options, asks):
    """The RelayedRuling of the call's relay options, or None when the call has none. Refuses the call (nothing is
    logged) when the relaying session holds no real user turn typed after the user-only asks of `asks` were
    filed. A user-only ask with no filed time is refused;
    `read_state` stamps one saved before filed times existed."""
    if options.relay is None:
        return None
    try:
        filed_at = ruling_relay.latest_filed_at(asks)
        return ruling_relay.verify_relay(options.relay, filed_at)
    except HumanTurnRefusedError as error:
        raise UsageError(f"{ruling_relay.relay_refusal_line(error)}. Nothing was logged.") from error


def record_unrecorded_relay(target, relayed, repo, new_indexes):
    """Stores the relayed ruling for the user-only asks of the packet `target` that this call logged (`new_indexes`)
    and that no earlier call recorded: an ask an earlier call logged with no relay is never credited to a later
    relay, a retry after a logging failure adds each finding once, and a failed ordinary ask does not hold the
    logged user-only asks back."""
    if relayed is None:
        return
    recorded = target.setdefault("asks_relay_recorded", [])
    logged_asks = [target["asks"][index] for index in new_indexes]
    fresh_asks = [item for item in logged_asks
                  if item.get(USER_ONLY_KEY) and item.get("finding_id") not in recorded]
    if not fresh_asks:
        return
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    ruling_relay.record_relay(session_id, repo, relayed, fresh_asks)
    recorded.extend(item.get("finding_id") for item in fresh_asks)


def finding_ask_indexes(asks, outcomes):
    """The indexes of the asks that go to the findings file: accepted or modified, and not a plan impact. A rejected
    ask and an applied one (already in the tree) have no change to make."""
    return [index for index, (item, outcome) in enumerate(zip(asks, outcomes, strict=True))
            if outcome not in (REJECTED, APPLIED) and not is_plan_impact_ask(item)]


def ruler_clause(decided_by):
    """The clause that names who changed a modified ask: the user, the session, or no one when `decided_by` is None.
    `ask_deciders` and `--by` refuse any other word, so none reaches here."""
    if decided_by == plan_format.USER_RULING:
        return USER_CLAUSE
    if decided_by == plan_format.SESSION_RULING:
        return SESSION_CLAUSE
    return UNNAMED_CLAUSE


def ask_finding_text(item, note=None, decided_by=None):
    """The finding text of an accepted ask: its location, class tag and proposed change, plus the ruler's `note`
    when the ask was modified (`decided_by` says who ruled), and the `acceptance_criteria:` ids of the question,
    change and note. A plan-impact ask keeps its question because the text is stored as the ruled impact's
    `finding_text`, which a later finding must equal word for word."""
    question = one_line(item["question"], None)
    change = one_line(item["change"], None)
    # A converted ask's change is the finding line the user already accepted: it holds its own proposed change.
    if item.get(USER_RULED_KEY):
        if note is None:
            return change
        return changed_text(change, note, ruler_clause(decided_by))
    if is_plan_impact_ask(item):
        return f"{item['file_line']} {question} Proposed change: {change}"
    # The question can hold a declined branch the user already ruled against; a coder that reads it may take it.
    # The ids of the question, change and note stay for the ruled-impact match; the appended
    # `acceptance_criteria:` line becomes the only source of ids, so it comes after the note.
    text = f"{item['file_line']} [{item['class']}] Proposed change: {change}"
    if note is not None:
        text = changed_text(text, note, ruler_clause(decided_by))
    ids = sorted(plan_format.criteria_ids(f"{question} {change} {note or ''}"))
    if ids:
        text += f" acceptance_criteria: {', '.join(ids)}"
    return text


def ask_finding_lines(asks, outcomes, notes, deciders):
    """One findings-file item per accepted or modified ask that is not a plan impact, in the form
    review_launch.read_findings_file reads. A modified ask carries its ruler's change in place of the proposed one."""
    return ["- " + text for text in accepted_finding_texts(asks, outcomes, notes, deciders)]


def accepted_finding_texts(asks, outcomes, notes, deciders):
    """The finding text of each accepted or modified ask that is not a plan impact, as the findings file holds it.
    `deciders` holds who ruled on each ask, in the order of `asks` (None for none)."""
    texts = []
    for index in finding_ask_indexes(asks, outcomes):
        item, outcome, note = asks[index], outcomes[index], notes[index]
        texts.append(ask_finding_text(item, note if outcome == MODIFIED else None, deciders[index]))
    return texts


def findings_covered_by_impact(state, impact_text):
    """The accepted finding texts of the packet in `state` whose criterion ids the ruled plan impact `impact_text`
    covers, so a ruling on the impact also settles those findings in a later fix run. [] when the packet holds no
    answered asks."""
    asks = state.get("asks") or []
    outcomes = state.get("ask_outcomes") or []
    notes = state.get("ask_notes") or []
    if not asks or len(outcomes) != len(asks) or len(notes) != len(asks):
        return []
    texts = accepted_finding_texts(asks, outcomes, notes, ask_deciders(state))
    covered = []
    for text in texts:
        criteria_ids = plan_item_criteria_ids(text)
        if criteria_covered(criteria_ids, [impact_text]):
            covered.append(text)
    return covered


def is_accepted_plan_impact(item, outcome):
    """Whether `item` is a plan-impact ask whose outcome is not a rejection."""
    return outcome != REJECTED and is_plan_impact_ask(item)


def accepted_ask_deviation_lines(asks, outcomes, notes, decided_by):
    """The `## Plan Deviations` entry lines for each accepted or modified plan-impact ask: the ask's proposed change
    is the disagreement; a modified ask's note is the ruling."""
    owner = plan_format.ruling_owner(".", decided_by)
    ruled_at = plan_format.ruled_at_now()
    choice = plan_format.DECISION_WORDS[plan_format.ADOPT_DECISION]
    lines = []
    for item, outcome, note in zip(asks, outcomes, notes, strict=True):
        if not is_accepted_plan_impact(item, outcome):
            continue
        change = one_line(item["change"], None)
        ruling = note if outcome == MODIFIED else "Adopted the proposed plan change."
        lines += plan_format.ruling_deviation(None, choice, owner, ruled_at, ruling, change)
    return lines


def packet_repo(relaunch_args):
    """The repo the review packet answers: the `--repo` its launch record (`relaunch_args`) carries, else the
    session's repo, as the top level of its work tree. Rows written under it are the ones that repo's loop reads."""
    launch_repo = review_launch.relaunch_repo(relaunch_args)
    if launch_repo is not None:
        return handback_store.ruled_rows_repo(launch_repo)
    return handback_store.ruled_rows_repo(session_repo())


def required_packet_repo(relaunch_args):
    """`packet_repo`, or a stop when it names no git work tree: a row written under no repo is one no later run
    reads."""
    repo = packet_repo(relaunch_args)
    if repo is not None:
        return repo
    raise UsageError(missing_packet_repo_reason(relaunch_args))


def missing_packet_repo_reason(relaunch_args):
    """The cause and recovery when `packet_repo` is None: the launch `--repo` is gone, the session's dispatched repo
    is gone, or there is neither and the current directory is not in a git work tree."""
    removed_text = "is no longer a git work tree (for example a removed worktree). Recreate the worktree at that " \
                   "path, or rerun the review from a live repo."
    launch_repo = review_launch.relaunch_repo(relaunch_args)
    if launch_repo is not None:
        return f"the launch record's --repo {launch_repo} {removed_text}"
    dispatched = dispatched_repo()
    if dispatched is not None:
        return f"the session's last dispatched repo {dispatched} {removed_text}"
    return ("the session has no dispatched repo and the current directory is not in a git work tree. "
            "Run it from inside the reviewed repo.")


def repo_for_outcomes(relaunch_args, asks, outcomes):
    """`required_packet_repo` when an outcome writes under the repo (a rejection, an accepted plan-impact ask, or a
    ruling on an approval ask, which leaves the saved approval paths), else None: an answer that writes nothing
    there needs no repo."""
    for item, outcome in zip(asks, outcomes, strict=True):
        if outcome == REJECTED or is_accepted_plan_impact(item, outcome) or is_approval_ask(item):
            return required_packet_repo(relaunch_args)
    return None


def record_accepted_plan_impacts(asks, outcomes, repo):
    """Records each accepted or modified plan-impact ask in the hand-back store as a ruled impact, so a later fix run
    of this repo leaves a finding on it out. The recorded text joins the question, which opens with the plan-impact
    mark, and the change, so it carries the `acceptance_criteria:` line wherever the ask put it; a later finding is
    matched on that line."""
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    for item, outcome in zip(asks, outcomes, strict=True):
        if not is_accepted_plan_impact(item, outcome):
            continue
        question = one_line(item["question"], None)
        change = one_line(item["change"], None)
        handback_store.record_ruled_impact(session_id, f"{question} — change: {change}", repo,
                                           finding_text=ask_finding_text(item))


def refuse_damaged_approval_paths(repo, asks):
    """Stops with nothing written when a ruled approval ask needs the saved approval paths and the file is
    damaged: a rerun would log every outcome row again."""
    try:
        check_approval_paths_readable(repo, asks)
    except ApprovalAsksFileError as error:
        raise UsageError(f"{error}. Nothing was logged.") from error


def record_corrected_rejection(item, old_outcome, new_outcome, repo):
    """Keeps the rejected-ask rows in step with a corrected answer: a new rejection is recorded, and a rejection the
    correction undoes is withdrawn. A corrected approval ask leaves the saved approval paths, whatever the new
    outcome."""
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    forget_ruled_approval_paths(repo, [item])
    if new_outcome == REJECTED:
        review_asks.record_rejection(session_id, item, repo)
    elif old_outcome == REJECTED:
        handback_store.record_rejection_withdrawn(session_id, rejected_ask_text(item), repo)


def record_ruled_asks_once(target, asks, outcomes, repo):
    """Records the packet's rejected asks once, and drops its ruled approval asks from the saved approval paths: a
    retry after a logging failure does neither again."""
    if target.get("asks_rejections_recorded"):
        return
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    review_asks.record_rejected_asks([session_id], repo, asks, outcomes)
    # A ruled approval ask leaves the saved paths, so a resumed review loop does not file it again.
    forget_ruled_approval_paths(repo, asks)
    target["asks_rejections_recorded"] = True


def summary_line(target, asks, ask_counts, decided_by, failures, held=False, retryable=True):
    rows_logged = sum(1 for index in target["asks_logged"] if not is_plan_impact_ask(asks[index]))
    summary = f"Logged {rows_logged} of {len(asks)} ask outcome row(s)."
    if decided_by == plan_format.SESSION_RULING:
        summary += " The session ruled, not the user."
    if ask_counts[PLAN_IMPACT_STATUS]:
        summary += f" {ask_counts[PLAN_IMPACT_STATUS]} plan-impact ask(s) are not logged as findings."
    if ask_counts[NEW_FINDING_ID]:
        summary += (f" {ask_counts[NEW_FINDING_ID]} ask(s) without a valid finding_id are logged under a new "
                    "finding_id.")
    if failures:
        retry_advice = "run the same asks-done again to retry only these"
        if held and retryable:
            retry_advice = "retry only these with the call in the held line below"
        summary += f" Failures (mention, never block; {retry_advice}):"
    return summary


def write_findings_file(finding_lines):
    """Writes the accepted asks to the findings file and returns its path."""
    findings_file = review_fix_dir() / ASK_FINDINGS_NAME
    script_utils.write_text_atomically(findings_file, "\n".join(finding_lines) + "\n")
    return findings_file


def print_fix_run(target, findings_file, summary_lines):
    """Prints the fix run that applies the accepted asks in findings_file. A run that left no launch record prints
    the stored line from `no_record_launch_line`: `--iter`, the cap flags (`--fix-rounds`, `--post-cap-passes`), the
    dispatched `--repo` and `--detach` only."""
    if not target.get("relaunch_args"):
        return print_action(
            NO_LAUNCH_RECORD_ACTION, *summary_lines,
            f"The accepted asks are in {findings_file}, but `review_fix.py launch` did not start this run, so no "
            "launch flags are on record. Run this launch line now: its fix coder applies them.",
            target["asks_launch_line"])

    return print_action(
        "redispatch", *summary_lines,
        f"The accepted asks are in {findings_file}. Run this launch line now: its fix coder applies them and a "
        "review round covers the fix. If findings were deferred to this run, write them to "
        f"<run folder>/{RUN_FOLDER_FINDINGS_NAME} and add `--also-fix <that file>` to the line.",
        target["asks_launch_line"])


def ask_deciders(state):
    """Who ruled on each ask of state: a list with one entry per ask, None for an ask nobody ruled on yet."""
    # A state with no key (before the first asks-done): no ask is on record as user-ruled.
    deciders = state.get(ASKS_DECIDED_BY_KEY)
    if deciders is None:
        return [None] * len(state["asks"])

    if not isinstance(deciders, list) or len(deciders) != len(state["asks"]):
        raise UsageError(f"{ASKS_DECIDED_BY_KEY} in the saved state must be a list with one entry per ask "
                         f"({len(state['asks'])}), not {deciders!r}.")
    for decider in deciders:
        if decider is not None and not plan_format.is_ruling_by(decider):
            raise UsageError(f"{ASKS_DECIDED_BY_KEY} in the saved state holds {decider!r}; each entry must be "
                             f"null, {plan_format.USER_RULING!r} or {plan_format.SESSION_RULING!r}.")
    return deciders


def uniform_deciders(asks, decided_by):
    """The deciders of a first asks-done call: `decided_by` ruled on every ask."""
    return [decided_by] * len(asks)


def set_ask_decider(state, index, decided_by):
    """Records who ruled on ask `index`: the latest decider of the ask's answer, so a session correction that
    changes a user-ruled ask's answer drops its user ruling."""
    deciders = ask_deciders(state)
    deciders[index] = decided_by
    state[ASKS_DECIDED_BY_KEY] = deciders


def ruled_numbers(state, ruler):
    """The 1-based positions, in the findings file, of the findings whose ask `ruler` ruled on."""
    deciders = ask_deciders(state)
    outcomes = approval_restore.finding_outcomes(state)
    indexes = finding_ask_indexes(state["asks"], outcomes)
    return [number for number, index in enumerate(indexes, 1) if deciders[index] == ruler]


def fix_lead_args(findings_file, user_numbers, session_numbers):
    """The leading launch flags of a fix run for findings_file. Each finding the user ruled on adds `--user-ruled N`,
    so the fix coder's skip of it comes back as an ask. Each finding a session ruled on adds `--session-ruled N`:
    the coder's re-ask of it is a skip, never an ask."""
    lead_args = ["--fix", str(findings_file)]
    for number in user_numbers:
        lead_args += ["--user-ruled", str(number)]
    for number in session_numbers:
        lead_args += ["--session-ruled", str(number)]
    return lead_args


def fix_launch_line(target, findings_file, user_numbers, session_numbers):
    """The launch line of the fix run that applies the asks in findings_file."""
    return relaunch_line(target, fix_lead_args(findings_file, user_numbers, session_numbers))


def relaunch_line(target, lead_args, handoff_file=None):
    """The launch line of a later run of the review in target: lead_args, `--iter`, the packet's `--fix-rounds` and
    `--post-cap-passes` (`review_launch.cap_count_args`), the first run's relaunch flags (with `--handoff` pointed
    at handoff_file when given) and `--detach`. The later run holds every dirty file not listed, and the first
    run's own edits are dirty, so the files it touched join the scoped files."""
    touched_paths = target.get("files_touched") or []
    relaunch_args = review_launch.relaunch_args_with_files(target["relaunch_args"], touched_paths)
    if handoff_file is not None:
        relaunch_args = review_launch.relaunch_args_with_handoff(relaunch_args, handoff_file)
    cap_args = review_launch.cap_count_args(target)
    launch_args = [*lead_args, "--iter", str(target["iter"]), *cap_args, *relaunch_args, "--detach"]
    return f"{LAUNCH_COMMAND} {shlex.join(launch_args)}"


def fix_run_launch_line(target, findings_file):
    """The launch line of the fix run for findings_file: the stored launch flags, or the bare line when the run left
    no launch record."""
    user_numbers = ruled_numbers(target, plan_format.USER_RULING)
    session_numbers = ruled_numbers(target, plan_format.SESSION_RULING)
    if target.get("relaunch_args"):
        return fix_launch_line(target, findings_file, user_numbers, session_numbers)
    return no_record_launch_line(target, findings_file, user_numbers, session_numbers)


def no_record_launch_line(target, findings_file, user_numbers, session_numbers):
    """The launch line of a fix run with no launch record: `--iter`, the packet's `--fix-rounds` and
    `--post-cap-passes` (`review_launch.cap_count_args`), the session's repo (`session_repo`) as `--repo` and
    `--detach` only."""
    repo = required_packet_repo([])
    lead_args = fix_lead_args(findings_file, user_numbers, session_numbers)
    cap_args = review_launch.cap_count_args(target)
    launch_args = [*lead_args, "--iter", str(target["iter"]), *cap_args, "--repo", str(repo), "--detach"]
    return f"{LAUNCH_COMMAND} {shlex.join(launch_args)}"


def unprinted_deviation_lines(target, asks, outcomes, notes, decided_by):
    """Returns the plan-deviation lines once per packet: a retry after a logging failure gets none."""
    if target.get("asks_deviations_printed"):
        return []
    deviation_lines = accepted_ask_deviation_lines(asks, outcomes, notes, decided_by)
    if deviation_lines:
        target["asks_deviations_printed"] = True
    return deviation_lines


def write_unprinted_fix_run(state, target, finding_lines, decided_by):
    """Writes the findings file for a fix run not yet printed and returns its path, else None. The write comes
    before the latch: a failed write leaves the state unlatched, so a retry prints the run. The launch line also
    goes to the top of state as pending, until the launch of that run clears it."""
    if not finding_lines or target.get("asks_redispatched"):
        return None
    findings_file = write_findings_file(finding_lines)
    target["asks_redispatched"] = True
    target[ASKS_DECIDED_BY_KEY] = uniform_deciders(target["asks"], decided_by)
    launch_line = fix_run_launch_line(target, findings_file)
    target["asks_launch_line"] = launch_line
    state[PENDING_LAUNCH_KEY] = launch_line
    return findings_file


def print_done_again(state):
    """A repeat asks-done with every ask logged. A stored fix run is printed again: the first call may have been
    cut off before its launch line was run. The held line is printed again too, as it gives the held packet's id
    and the user's call."""
    done_line = "The ask outcomes were already logged."
    held_id = held_packet_id(state.get("packet_id", ""))
    held_lines = []
    for packet in state.get("waiting_packets") or []:
        if packet["packet_id"] == held_id:
            held_lines = held_summary_lines(packet, state["packet_id"], retryable=True)
    launch_line = state.get("last_asks_launch_line")
    if not launch_line:
        return print_action("done", done_line, "Run nothing more.", *held_lines)
    return print_action("done", done_line, PRINTED_RUN_LINE, launch_line, *held_lines)


def mark_packet_answered(state, target):
    """Records that every ask of target was logged: the state is done, or target leaves the waiting packets."""
    if target is state:
        state["stage"] = "done"
    else:
        state["waiting_packets"] = [kept for kept in state["waiting_packets"] if kept is not target]
    state["last_asks_launch_line"] = target.get("asks_launch_line")
    state["last_ask_outcomes"] = target.get("ask_outcomes")
    state["last_ask_notes"] = target.get("ask_notes")


def answer_of(outcome, note):
    """What an ask's answer is: the outcome word, plus the ruler's change for a modified one. The note after accepted
    or rejected is not stored."""
    return (outcome, note if outcome == MODIFIED else "")


def corrected_ask_indexes(state, asks, outcomes, notes):
    """The indexes of the asks whose answer differs from the one logged. Refuses when no earlier answers are on
    record, when a changed ask is a plan
    impact (--correct does not change those), and when no ask is left to correct."""
    logged_outcomes = state.get("ask_outcomes")
    logged_notes = state.get("ask_notes")
    if logged_outcomes is None or logged_notes is None:
        raise UsageError("--correct found no logged answers in the saved state, so it cannot tell which ask changed.")

    indexes = []
    for index, item in enumerate(asks):
        logged = answer_of(logged_outcomes[index], logged_notes[index])
        # An ask repeated unchanged keeps its earlier decider.
        if logged == answer_of(outcomes[index], notes[index]):
            continue
        if is_plan_impact_ask(item):
            raise UsageError(f"ask {index + 1} is a plan-impact ask: --correct does not change plan-impact asks. "
                             "Put the ruling into the plan's `## Plan Deviations` by hand.")
        indexes.append(index)
    if not indexes:
        raise UsageError("every outcome given matches the one already logged: nothing to correct.")
    return indexes


def log_corrected_outcomes(state, indexes, outcomes, notes, decided_by, relayed=None):
    """Logs a new outcome row for each corrected ask, under the finding_id the ask was first logged with. A row
    that logged joins the stored answers and is saved, so a retry logs only the rows that failed. The relayed ruling
    (when given) is stored for the user-only asks that logged, even when another row failed, because a retry no
    longer lists them. A failed row stops the correction after the findings file and the pending launch are rebuilt
    from the stored answers, so the printed run never applies an ask whose logged answer is rejected."""
    failures = []
    logged_asks = []
    corrected_asks = [state["asks"][index] for index in indexes]
    touches_rejection = any(REJECTED in (state["ask_outcomes"][index], outcomes[index]) for index in indexes)
    needs_repo = touches_rejection or any(is_approval_ask(item) for item in corrected_asks)
    repo = required_packet_repo(state.get("relaunch_args") or []) if needs_repo else None
    refuse_damaged_approval_paths(repo, corrected_asks)
    approval_restore.refuse_corrections_of_state(state, indexes, outcomes)
    for index in indexes:
        item = state["asks"][index]
        outcome_row = review_asks.log_ask_outcome(ASK_LOGGER, state, item, outcomes[index], decided_by)
        if outcome_row.code != 0:
            failures.append(outcome_failure_line(item, outcome_row))
            continue
        item["finding_id"] = outcome_row.finding_id
        record_corrected_rejection(item, state["ask_outcomes"][index], outcomes[index], repo)
        state["ask_outcomes"][index] = outcomes[index]
        state["ask_notes"][index] = notes[index]
        set_ask_decider(state, index, decided_by)
        logged_asks.append(item)
    if relayed is not None:
        session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
        ruling_relay.record_relay(session_id, repo, relayed, logged_asks)
    if not failures:
        return
    findings_file = sync_pending_fix_run(state)
    # The sync drops the pending launch when no ask has a change left to apply (every ask rejected or applied); the
    # retry must still be allowed. With a pending launch the guard on that launch covers the retry, and a launched
    # run must refuse it.
    if findings_file is None:
        state[CORRECT_OPEN_KEY] = True
    else:
        state.pop(CORRECT_OPEN_KEY, None)
    save_fix_state(state)
    raise UsageError("a corrected outcome row did not log. Rows that did log stay logged and are not logged again; "
                     "run the same call again to retry the rest:\n"
                     + "\n".join("- " + failure for failure in failures))


def sync_pending_fix_run(state):
    """Rebuilds the findings file and the pending launch from the stored answers and deciders, or drops both when no
    ask is left to apply. Does not save. Returns the findings file, or None when it was dropped."""
    finding_outcomes = approval_restore.finding_outcomes(state)
    finding_lines = ask_finding_lines(state["asks"], finding_outcomes, state["ask_notes"], ask_deciders(state))
    state["last_ask_outcomes"] = state["ask_outcomes"]
    state["last_ask_notes"] = state["ask_notes"]
    if not finding_lines:
        review_fix_dir().joinpath(ASK_FINDINGS_NAME).unlink(missing_ok=True)
        state.pop(PENDING_LAUNCH_KEY, None)
        state.pop("asks_launch_line", None)
        state["last_asks_launch_line"] = None
        return None

    findings_file = write_findings_file(finding_lines)
    launch_line = fix_run_launch_line(state, findings_file)
    state["asks_launch_line"] = launch_line
    state["last_asks_launch_line"] = launch_line
    state[PENDING_LAUNCH_KEY] = launch_line
    return findings_file


def correct_blocker(state):
    """The reason --correct cannot change the logged answers of this state, or None when it can."""
    pending_line = state.get(PENDING_LAUNCH_KEY)
    if not pending_line and not state.get(CORRECT_OPEN_KEY):
        return ("--correct needs a fix run that asks-done printed and that has not launched. None is "
                "pending: the printed fix run already launched, or asks-done printed none (every ask "
                "rejected, applied or plan-impact), or an earlier --correct left no ask to apply.")
    if state.get("asks_launch_line") != pending_line:
        return ("the pending fix run belongs to an earlier packet whose answers are no longer kept, so "
                "--correct cannot change them.")
    if state.get("stage") != "done":
        return ("the first asks-done still has unlogged asks. Finish it with the same plain asks-done call, "
                "then run --correct.")
    return None


def refuse_unless_correctable(state, packet_id):
    """Refuses --correct with no pending printed run, with a pending run of an earlier packet, while the first
    asks-done still has unlogged asks, and for a packet other than the current one."""
    blocker = correct_blocker(state)
    if blocker:
        raise UsageError(blocker)
    if packet_id is not None and packet_id != state["packet_id"]:
        raise UsageError(f"--correct only re-answers the current packet: --packet named {packet_id!r}, the current "
                         f"packet is {state['packet_id']!r}.")


def refuse_session_on_user_only(asks, decided_by, user_command, outcomes, holdable=False):
    """Refuses (nothing is logged) a `--by session` answer to an ask marked `user_only`. `user_command` is the
    call the refusal tells the session to use for the user's ruling; `outcomes` (one per ask) lets a `rejected` on
    a wanted-change ask pass; `holdable` makes it name `held` too."""
    refusal = review_asks.user_only_refusal(asks, decided_by, user_command, outcomes, holdable)
    if refusal:
        raise UsageError(refusal)


def command_correct_asks(options):
    """`asks-done --correct <outcome>...`: re-answers the asks of a fix run that printed and has not launched. Each
    new row is logged under the ask's earlier finding_id and supersedes the old row, the findings file is rewritten
    from the corrected answers, and the launch line is printed again, or the pending flag is cleared when no ask is
    left to apply."""
    state = load_fix_state()
    refuse_unless_correctable(state, options.packet_id)
    deciders = ask_deciders(state)  # a bad saved ruler stops the run before any row is logged

    asks = state["asks"]
    outcomes, notes = read_outcomes(options.outcome_words, asks)
    review_asks.refuse_conditional_changes(asks, outcomes, "asks-done --correct ...")
    review_asks.refuse_unlocated_changes(asks, outcomes, notes, "asks-done --correct ...")
    indexes = corrected_ask_indexes(state, asks, outcomes, notes)
    # Blank the uncorrected asks, keeping their places, so the refusal names only corrected user_only asks by
    # their listing numbers.
    corrected_asks = [item if index in indexes else {} for index, item in enumerate(asks)]
    user_command = f"asks-done --correct --by {plan_format.USER_RULING} ..."
    # A user's ruling is never replaced by a session: a None outcome keeps that ask refused.
    session_outcomes = [None if decider == plan_format.USER_RULING else outcome
                        for decider, outcome in zip(deciders, outcomes, strict=True)]
    refuse_session_on_user_only(corrected_asks, options.decided_by, user_command, session_outcomes)
    relayed = verified_fix_relay(options, corrected_asks)
    log_corrected_outcomes(state, indexes, outcomes, notes, options.decided_by, relayed)

    summary = f"Corrected {len(indexes)} ask outcome row(s)."
    findings_file = sync_pending_fix_run(state)
    state.pop(CORRECT_OPEN_KEY, None)
    save_fix_state(state)
    if not findings_file:
        return print_action("done", summary, "No ask is left with a change to make, so no fix run is pending. "
                            "Run nothing more.")
    return print_fix_run(state, findings_file, [summary])


class HeldChanges(NamedTuple):
    """The approval changes of the held asks of one call, and the repo whose approval store holds them."""
    repo: str
    changes: list


class Answers(NamedTuple):
    """What an asks-done call answers: the packet, its outcome words and notes, who decided, the kept
    packet that holds the asks the call held (None when it held none) and the approval changes of those asks
    (None when it held none). After a hold, `target` and the outcomes cover the plain asks only."""
    target: dict
    outcomes: list
    notes: list
    decided_by: str
    held_packet: dict | None
    held_changes: HeldChanges | None


# The keys of a packet's state that its held asks keep: the kept packet relaunches the same review run.
HELD_PACKET_KEYS = (*PACKET_IDENTITY_KEYS, "relaunch_args")
HELD_PACKET_SUFFIX = "-held"


def held_packet_id(packet_id):
    """The id of the kept packet that holds the held asks of the packet `packet_id`."""
    return packet_id + HELD_PACKET_SUFFIX


def held_approval_changes(target, held_asks):
    """The HeldChanges of `held_asks`, which the call writes once its state is saved (`command_asks_done`). Refuses
    (nothing is logged) when the repo's held-changes file is damaged, so the later write cannot fail."""
    packet_repo_path = required_packet_repo(target.get("relaunch_args") or [])
    try:
        read_held_changes(packet_repo_path)
    except ApprovalAsksFileError as error:
        raise UsageError(f"{error}. Nothing was logged.") from error
    return HeldChanges(packet_repo_path, user_only_changes(held_asks))


def keep_held_packet(state, target, held_asks):
    """Moves held_asks into a new kept packet of `state` (its own packet id, the parent's relaunch args) that waits
    for the user's `--by user --packet <id>` call, and returns it. Writes nothing to disk: the held approval
    changes are written by `command_asks_done` after the state is saved."""
    held_id = held_packet_id(target["packet_id"])
    held_packet = {key: target[key] for key in HELD_PACKET_KEYS if key in target}
    held_packet.update({"packet_id": held_id, "stage": "asks", "asks": held_asks})
    state.setdefault("waiting_packets", []).append(held_packet)
    return held_packet


def read_answers(state, options, waiting):
    """The Answers of an asks-done call. Refuses a bad answer before anything is logged, and a retry that answers
    differently from the outcomes already logged. Those answers stay on the packet, as the logged rows and the
    findings file hold them, so `--correct` can tell which ask changed. A `held` ask leaves the packet for a new
    kept one once every check has passed."""
    target = choose_asks_packet(waiting, options.packet_id)
    asks = target["asks"]
    outcomes, notes = read_outcomes(options.outcome_words, asks, allow_held=True)
    refuse_misplaced_held(target, outcomes, options.decided_by)
    split = split_held(asks, outcomes, notes)
    # The held asks are not ruled: blank them, keeping their places, so the refusals skip them and name the
    # asks by their numbers in the stop's order.
    kept_places = [{} if outcome == HELD else item for item, outcome in zip(asks, outcomes, strict=True)]
    user_command = f"asks-done --by {plan_format.USER_RULING} ..."
    refuse_session_on_user_only(kept_places, options.decided_by, user_command, outcomes, holdable=True)
    review_asks.refuse_conditional_changes(kept_places, outcomes, "asks-done ...")
    review_asks.refuse_unlocated_changes(kept_places, outcomes, notes, "asks-done ...")
    refuse_changed_retry(state, target, split.plain_outcomes, split.plain_notes, correctable=False)

    held_packet = None
    held_changes = None
    if split.held_asks:
        held_changes = held_approval_changes(target, split.held_asks)
        target["asks"] = split.plain_asks
        held_packet = keep_held_packet(state, target, split.held_asks)
    target.setdefault("ask_outcomes", split.plain_outcomes)
    target.setdefault("ask_notes", split.plain_notes)
    return Answers(target, split.plain_outcomes, split.plain_notes, options.decided_by, held_packet, held_changes)


def held_summary_lines(held_packet, parent_id, retryable):
    """The summary lines that say where the held asks wait and how the user rules them. When the call that held the
    asks can be retried (its packet is the current one, or a row failed to log), they also say how to retry it."""
    if held_packet is None:
        return []
    held_id = held_packet["packet_id"]
    line = (f"{len(held_packet['asks'])} user_only ask(s) are {HELD}, unruled, in packet {held_id}. The user rules "
            f"them with `asks-done --by {plan_format.USER_RULING} --packet {held_id} <outcome>...`.")
    if retryable:
        line += (f" A retry of this call is `asks-done --by {plan_format.SESSION_RULING} --packet {parent_id} "
                 "<plain outcomes>`, the outcomes of the plain asks only.")
    return [line]


def refuse_changed_retry(state, target, outcomes, notes, correctable):
    """Refuses a retry of asks-done whose answers differ from the outcomes already logged, which the logged rows and
    the findings file hold. Names `--correct` only when the caller says it re-answers these logged answers; else
    the refusal gives the reason `--correct` cannot."""
    logged_outcomes = target.get("ask_outcomes")
    logged_notes = target.get("ask_notes")
    if logged_outcomes is None or logged_notes is None:
        return
    for index, outcome in enumerate(outcomes):
        if answer_of(logged_outcomes[index], logged_notes[index]) == answer_of(outcome, notes[index]):
            continue
        if correctable:
            raise UsageError("asks-done is a retry: rerun it with the outcomes already logged, then use --correct to "
                             "change an answer.")
        if any(kept is target for kept in state.get("waiting_packets") or []):
            raise UsageError("asks-done is a retry: rerun it with the outcomes already logged. --correct only "
                             "re-answers the current packet, not a kept one.")
        blocker = correct_blocker(state) or "--correct only re-answers the current packet."
        raise UsageError("asks-done is a retry: rerun it with the outcomes already logged. --correct cannot change "
                         "them: " + blocker)


def repeat_done_asks(state, options):
    """An asks-done call with no packet waiting, or a retry of a finished call that held asks
    (`is_retry_of_done_packet`): a retry of the finished call prints its result again, with the same
    outcomes as the ones already logged. Anything else is refused."""
    last_outcomes = state.get("last_ask_outcomes")
    if state.get("stage") != "done" or not last_outcomes:
        raise UsageError("no asks are waiting. `asks-done` follows a packet that carried ask[] entries.")
    if len(options.outcome_words) != len(last_outcomes):
        raise UsageError(f"asks-done is a retry: give the {len(last_outcomes)} outcome(s) already logged, "
                         f"not {len(options.outcome_words)}.")
    outcomes, notes = read_outcomes(options.outcome_words, last_outcomes)
    logged = {"ask_outcomes": last_outcomes, "ask_notes": state["last_ask_notes"]}
    correctable = (correct_blocker(state) is None
                   and state.get("last_asks_launch_line") == state.get(PENDING_LAUNCH_KEY))
    refuse_changed_retry(state, logged, outcomes, notes, correctable)
    return print_done_again(state)


def is_retry_of_done_packet(state, waiting, options):
    """Whether an asks-done call retries the finished current packet's call: the call names that packet, or names
    none while only its kept held packet waits. Only a session call holds asks, so only a session call that names
    no packet retries a hold; a user call then rules the held packet."""
    if state.get("stage") != "done":
        return False
    if options.packet_id is not None:
        return options.packet_id == state.get("packet_id")
    if options.decided_by != plan_format.SESSION_RULING:
        return False
    held_id = held_packet_id(state.get("packet_id", ""))
    return all(packet["packet_id"] == held_id for packet in waiting)


def command_asks_done(argv):
    options = asks_done_options(argv)
    if options.correct:
        return command_correct_asks(options)

    state = load_fix_state()
    waiting = waiting_ask_packets(state)
    if not waiting or is_retry_of_done_packet(state, waiting, options):
        return repeat_done_asks(state, options)

    target, outcomes, notes, decided_by, held_packet, held_changes = read_answers(state, options, waiting)
    asks = target["asks"]
    relayed = verified_fix_relay(options, asks)
    repo = repo_for_outcomes(target.get("relaunch_args") or [], asks, outcomes)
    refuse_damaged_approval_paths(repo, asks)
    finding_outcomes = approval_restore.restore_for_asks_done(target, repo, outcomes)
    finding_lines = ask_finding_lines(asks, finding_outcomes, notes, uniform_deciders(asks, decided_by))
    findings_file = write_unprinted_fix_run(state, target, finding_lines, decided_by)

    logged_now = log_fix_ask_outcomes(target, asks, outcomes, decided_by)
    ask_counts, failures = logged_now.ask_counts, logged_now.failures
    # A kept parent has left the waiting packets, so its call is retryable only while a row failed to log.
    retryable = target is state or bool(failures)
    summary_lines = [summary_line(target, asks, ask_counts, decided_by, failures, held_packet is not None, retryable),
                     *["- " + failure for failure in failures],
                     *held_summary_lines(held_packet, target["packet_id"], retryable)]
    deviation_lines = unprinted_deviation_lines(target, asks, outcomes, notes, decided_by)
    record_ruled_asks_once(target, asks, outcomes, repo)
    record_unrecorded_relay(target, relayed, repo, logged_now.new_indexes)
    if deviation_lines:
        record_accepted_plan_impacts(asks, outcomes, repo)
        summary_lines += [ADD_DEVIATIONS_LINE, *deviation_lines]

    if findings_file:
        # Only the first print removes a fix-findings.md an earlier run left, so the launch cannot read it; a later
        # --correct print must keep the one the session wrote for this run. It runs before the save that latches
        # the print, so a crash between the two lets the retry remove it.
        run_repo = packet_repo(target.get("relaunch_args") or [])
        if run_repo is not None and review_launch.remove_stale_run_folder_findings(run_repo):
            summary_lines += [STALE_RUN_FOLDER_FINDINGS_REMOVED]

    if not failures:
        mark_packet_answered(state, target)
    save_fix_state(state)
    # After the save: a crash before it leaves no held record that no saved kept packet holds, which a later loop
    # would skip for good. A crash after the save only lets the loop file the ask again.
    if held_changes is not None:
        write_held_changes(held_changes.repo, held_changes.changes)

    if findings_file:
        print_fix_run(target, findings_file, summary_lines)
    elif target.get("asks_launch_line"):
        print_action("done", *summary_lines,
                     PRINTED_RUN_LINE, target["asks_launch_line"])
    else:
        print_action("done", *summary_lines)
    if not failures:
        record_packet_asks_logged(target["packet_id"])
    return 0
