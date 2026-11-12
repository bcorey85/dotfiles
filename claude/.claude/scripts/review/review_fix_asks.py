"""review_fix_asks.py: `review_fix.py asks-done`. It logs one outcome row per ask, once; `--correct` logs one more row
for each corrected ask while the printed fix run has not launched. When the user accepted or modified an ask, it
writes those asks to a findings file and prints the fix run that applies them: the first run's launch flags plus
`--fix`, `--iter` and `--detach`, so the loop's fix coder makes the change, a review round covers it, and the
converged hand-back earns commit credit."""
import pathlib
import shlex
import sys
from typing import NamedTuple

import plan_format
import review_asks
import review_launch
import script_utils
from handback import PLAN_IMPACT_STATUS, is_plan_impact_ask
from review_asks import ACCEPT_MEANS, ACCEPTED, ASK_OUTCOMES, MODIFIED, REJECT_MEANS, REJECTED, USER_RULED_KEY
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
from saved_handback import dispatched_repo
from script_utils import one_line, split_location

NEW_FINDING_ID = "new-finding-id"
CORRECT_FLAG = "--correct"
LAUNCH_COMMAND = f"{REVIEW_FIX_COMMAND} launch"
NO_LAUNCH_RECORD_ACTION = "launch-fix-run"
PRINTED_RUN_LINE = "The first asks-done printed this fix run; run it now unless it already ran."


def read_outcomes(argv, asks):
    """(the outcome word of each ask, the note after `:` of each, "" when none). A modified ask needs its note: the
    note is the user's change."""
    if len(argv) != len(asks):
        raise UsageError(f"{len(asks)} ask(s) waiting but {len(argv)} outcome(s) given")
    outcomes, notes = [], []
    for number, word in enumerate(argv, 1):
        outcome, _separator, note = word.partition(":")
        if outcome not in ASK_OUTCOMES:
            raise UsageError(
                f"outcome {word!r} is not one of {'|'.join(ASK_OUTCOMES)}. {ACCEPTED}: {ACCEPT_MEANS}; "
                f"{REJECTED}: {REJECT_MEANS} (the outcome for a 'leave it' or 'accept the gap' "
                f"option); {MODIFIED}:<change>: make that change instead")
        if outcome == MODIFIED and not note.strip():
            raise UsageError(f"outcome {number} is modified with no note; "
                             f"write '{MODIFIED}:<the user's change>' quoted as one shell word")
        outcomes.append(outcome)
        notes.append(one_line(note, None))
    return outcomes, notes


def outcome_failure_line(item, outcome_row):
    """The failure line of an ask outcome row that did not log."""
    path, line = split_location(item.get("file_line") or "-")
    return f"{path}:{line}: {one_line(outcome_row.output, 160)}"


def log_fix_ask_outcomes(state, asks, outcomes, decided_by):
    """(ask counts of this call: plan-impact asks skipped, outcomes logged under a new finding_id; failure lines). An
    ask that is logged or skipped joins asks_logged and is never tried again."""
    logged = state.setdefault("asks_logged", [])
    ask_counts = {PLAN_IMPACT_STATUS: 0, NEW_FINDING_ID: 0}
    failures = []
    for index, (item, outcome) in enumerate(zip(asks, outcomes, strict=True)):
        if index in logged:
            continue

        outcome_row = review_asks.log_ask_outcome(ASK_LOGGER, state, item, outcome, decided_by)
        if outcome_row is None:
            ask_counts[PLAN_IMPACT_STATUS] += 1
            logged.append(index)
            continue
        if outcome_row.code == 0:
            logged.append(index)
            # A minted id is kept so a later `--correct` row supersedes this one.
            item["finding_id"] = outcome_row.finding_id
            if outcome_row.new_finding_id_note:
                print(f"review-fix: {outcome_row.new_finding_id_note}", file=sys.stderr)
                ask_counts[NEW_FINDING_ID] += 1
            continue
        failures.append(outcome_failure_line(item, outcome_row))
    return ask_counts, failures


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


def asks_done_options(argv):
    """The AsksDoneOptions of an asks-done call."""
    outcome_words, decided_by = script_utils.pop_option(argv, "--by")
    if decided_by is None:
        raise UsageError("asks-done needs --by: `--by user` when the user gave the answer, `--by session` when "
                         "the session ruled on the asks itself.")
    if not plan_format.is_ruling_by(decided_by):
        raise UsageError(f"asks-done --by needs user or session, not {decided_by!r}")

    outcome_words, packet_id = script_utils.pop_option(outcome_words, "--packet")
    if packet_id == "":
        raise UsageError("asks-done --packet needs a packet_id")
    correct = CORRECT_FLAG in outcome_words
    outcome_words = [word for word in outcome_words if word != CORRECT_FLAG]
    return AsksDoneOptions(outcome_words, decided_by, packet_id, correct)


def finding_ask_indexes(asks, outcomes):
    """The indexes of the asks that go to the findings file: accepted or modified, and not a plan impact."""
    return [index for index, (item, outcome) in enumerate(zip(asks, outcomes, strict=True))
            if outcome != REJECTED and not is_plan_impact_ask(item)]


def ask_finding_lines(asks, outcomes, notes):
    """One findings-file item per accepted or modified ask that is not a plan impact, in the form
    review_launch.read_findings_file reads. A modified ask carries the user's change in place of the proposed one."""
    lines = []
    for index in finding_ask_indexes(asks, outcomes):
        item, outcome, note = asks[index], outcomes[index], notes[index]
        question = one_line(item["question"], None)
        change = one_line(item["change"], None)
        text = f"{item['file_line']} {question} Proposed change: {change}"
        # A converted ask's change is the finding line the user already accepted: it holds its own proposed change.
        if item.get(USER_RULED_KEY):
            text = change
        if outcome == MODIFIED:
            text += f" The user changed it; make this change in its place: {note}"
        lines.append("- " + text)
    return lines


def accepted_ask_deviation_lines(asks, outcomes, notes, decided_by):
    """The `## Plan Deviations` entry lines for each accepted or modified plan-impact ask: the ask's proposed change
    is the disagreement; a modified ask's note is the ruling."""
    owner = plan_format.ruling_owner(".", decided_by)
    ruled_at = plan_format.ruled_at_now()
    choice = plan_format.DECISION_WORDS["adopt"]
    lines = []
    for item, outcome, note in zip(asks, outcomes, notes, strict=True):
        if outcome == REJECTED or not is_plan_impact_ask(item):
            continue
        change = one_line(item["change"], None)
        ruling = note if outcome == MODIFIED else "Adopted the proposed plan change."
        lines += plan_format.ruling_deviation(None, choice, owner, ruled_at, ruling, change)
    return lines


def summary_line(target, asks, ask_counts, decided_by, failures):
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
        summary += " Failures (mention, never block; run the same asks-done again to retry only these):"
    return summary


def write_findings_file(finding_lines):
    """Writes the accepted asks to the findings file and returns its path."""
    findings_file = review_fix_dir() / ASK_FINDINGS_NAME
    script_utils.write_text_atomically(findings_file, "\n".join(finding_lines) + "\n")
    return findings_file


def print_fix_run(target, findings_file, summary_lines):
    """Prints the fix run that applies the accepted asks in findings_file. A run that left no launch record prints
    the stored line from `no_record_launch_line`: `--iter`, the dispatched `--repo` and `--detach` only."""
    if not target.get("relaunch_args"):
        return print_action(
            NO_LAUNCH_RECORD_ACTION, *summary_lines,
            f"The accepted asks are in {findings_file}, but `review_fix.py launch` did not start this run, so no "
            "launch flags are on record. Run this launch line now: its fix coder applies them.",
            target["asks_launch_line"])

    return print_action(
        "redispatch", *summary_lines,
        f"The accepted asks are in {findings_file}. Run this launch line now: its fix coder applies them and a "
        "review round covers the fix.",
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
    return deciders


def set_ask_decider(state, index, decided_by):
    """Records who ruled on ask `index`: the latest decider of the ask's answer, so a session correction that
    changes a user-ruled ask's answer drops its user ruling."""
    deciders = ask_deciders(state)
    deciders[index] = decided_by
    state[ASKS_DECIDED_BY_KEY] = deciders


def user_ruled_numbers(state):
    """The 1-based positions, in the findings file, of the findings whose ask the user ruled on."""
    deciders = ask_deciders(state)
    indexes = finding_ask_indexes(state["asks"], state["ask_outcomes"])
    return [number for number, index in enumerate(indexes, 1) if deciders[index] == plan_format.USER_RULING]


def fix_lead_args(findings_file, user_numbers):
    """The leading launch flags of a fix run for findings_file. Each finding the user ruled on adds `--user-ruled N`,
    so the fix coder's skip of it comes back as an ask; a finding a session ruled on adds none."""
    lead_args = ["--fix", str(findings_file)]
    for number in user_numbers:
        lead_args += ["--user-ruled", str(number)]
    return lead_args


def fix_launch_line(target, findings_file, user_numbers):
    """The launch line of the fix run that applies the asks in findings_file."""
    return relaunch_line(target, fix_lead_args(findings_file, user_numbers))


def relaunch_line(target, lead_args, handoff_file=None):
    """The launch line of a later run of the review in target: lead_args, `--iter`, the first run's relaunch flags
    (with `--handoff` pointed at handoff_file when given) and `--detach`. The later run holds every dirty file not
    listed, and the first run's own edits are dirty, so the files it touched join the scoped files."""
    touched_paths = target.get("files_touched") or []
    relaunch_args = review_launch.relaunch_args_with_files(target["relaunch_args"], touched_paths)
    if handoff_file is not None:
        relaunch_args = review_launch.relaunch_args_with_handoff(relaunch_args, handoff_file)
    launch_args = [*lead_args, "--iter", str(target["iter"]), *relaunch_args, "--detach"]
    return f"{LAUNCH_COMMAND} {shlex.join(launch_args)}"


def fix_run_launch_line(target, findings_file):
    """The launch line of the fix run for findings_file: the stored launch flags, or the bare line when the run left
    no launch record."""
    user_numbers = user_ruled_numbers(target)
    if target.get("relaunch_args"):
        return fix_launch_line(target, findings_file, user_numbers)
    return no_record_launch_line(target, findings_file, user_numbers)


def no_record_launch_line(target, findings_file, user_numbers):
    """The launch line of a fix run with no launch record: `--iter`, the dispatched `--repo` and `--detach` only."""
    repo = dispatched_repo() or pathlib.Path.cwd()
    launch_args = [*fix_lead_args(findings_file, user_numbers), "--iter", str(target["iter"]), "--repo", str(repo),
                   "--detach"]
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
    target[ASKS_DECIDED_BY_KEY] = [decided_by] * len(target["asks"])
    launch_line = fix_run_launch_line(target, findings_file)
    target["asks_launch_line"] = launch_line
    state[PENDING_LAUNCH_KEY] = launch_line
    return findings_file


def print_done_again(state):
    """A repeat asks-done with every ask logged. A stored fix run is printed again: the first call may have been
    cut off before its launch line was run."""
    done_line = "The ask outcomes were already logged."
    launch_line = state.get("last_asks_launch_line")
    if not launch_line:
        return print_action("done", done_line, "Run nothing more.")
    return print_action("done", done_line, PRINTED_RUN_LINE, launch_line)


def mark_packet_answered(state, target):
    """Records that every ask of target was logged: the state is done, or target leaves the waiting packets."""
    if target is state:
        state["stage"] = "done"
    else:
        state["waiting_packets"] = [kept for kept in state["waiting_packets"] if kept is not target]
    state["last_asks_launch_line"] = target.get("asks_launch_line")
    state["last_ask_outcomes"] = target.get("ask_outcomes")
    state["last_ask_notes"] = target.get("ask_notes")


def refuse_conditional_changes(asks, outcomes):
    """Refuses an accepted or rejected outcome on an ask whose proposed change is conditional: neither word says
    which branch the user chose. A modified outcome carries the user's own change and is never refused."""
    problems = []
    for number, (item, outcome) in enumerate(zip(asks, outcomes, strict=True), 1):
        change = item.get("change") or ""
        # A converted ask's change is the skipped finding line the user already accepted; any "if" in it is not a
        # branch for the user to pick.
        if outcome == MODIFIED or item.get(USER_RULED_KEY) or not review_asks.is_conditional_change(change):
            continue
        problems.append(f"ask {number} ({item.get('file_line') or 'no file:line'}) has a conditional proposed "
                        f"change: {one_line(change, 160)}")
    if problems:
        raise UsageError("\n".join(problems) + "\nNothing was logged. Answer each of these asks with "
                         f"'{MODIFIED}:<the change to make, with no condition>', quoted as one shell word, and run "
                         "asks-done again.")


def answer_of(outcome, note):
    """What an ask's answer is: the outcome word, plus the user's change for a modified one. The note after accepted
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


def log_corrected_outcomes(state, indexes, outcomes, notes, decided_by):
    """Logs a new outcome row for each corrected ask, under the finding_id the ask was first logged with. A row that
    logged joins the stored answers and is saved, so a retry logs only the rows that failed. A failed row stops the
    correction after the findings file and the pending launch are rebuilt from the stored answers, so the printed run
    never applies an ask whose logged answer is rejected."""
    failures = []
    for index in indexes:
        item = state["asks"][index]
        outcome_row = review_asks.log_ask_outcome(ASK_LOGGER, state, item, outcomes[index], decided_by)
        if outcome_row.code != 0:
            failures.append(outcome_failure_line(item, outcome_row))
            continue
        item["finding_id"] = outcome_row.finding_id
        state["ask_outcomes"][index] = outcomes[index]
        state["ask_notes"][index] = notes[index]
        set_ask_decider(state, index, decided_by)
    if not failures:
        return
    findings_file = sync_pending_fix_run(state)
    # The sync drops the pending launch when every ask now reads rejected; the retry must still be allowed. With a
    # pending launch the guard on that launch covers the retry, and a launched run must refuse it.
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
    finding_lines = ask_finding_lines(state["asks"], state["ask_outcomes"], state["ask_notes"])
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
                "rejected or plan-impact), or an earlier --correct left no ask to apply.")
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


def command_correct_asks(options):
    """`asks-done --correct <outcome>...`: re-answers the asks of a fix run that printed and has not launched. Each
    new row is logged under the ask's earlier finding_id and supersedes the old row, the findings file is rewritten
    from the corrected answers, and the launch line is printed again, or the pending flag is cleared when no ask is
    left to apply."""
    state = load_fix_state()
    refuse_unless_correctable(state, options.packet_id)

    asks = state["asks"]
    outcomes, notes = read_outcomes(options.outcome_words, asks)
    refuse_conditional_changes(asks, outcomes)
    indexes = corrected_ask_indexes(state, asks, outcomes, notes)
    log_corrected_outcomes(state, indexes, outcomes, notes, options.decided_by)

    summary = f"Corrected {len(indexes)} ask outcome row(s)."
    findings_file = sync_pending_fix_run(state)
    state.pop(CORRECT_OPEN_KEY, None)
    save_fix_state(state)
    if not findings_file:
        return print_action("done", summary, "No accepted or modified ask is left, so no fix run is pending. "
                            "Run nothing more.")
    return print_fix_run(state, findings_file, [summary])


class Answers(NamedTuple):
    """What an asks-done call answers: the packet, its outcome words and notes, and who decided."""
    target: dict
    outcomes: list
    notes: list
    decided_by: str


def read_answers(state, options, waiting):
    """The Answers of an asks-done call. Refuses a bad answer before anything is logged, and a retry that answers
    differently from the outcomes already logged. Those answers stay on the packet, as the logged rows and the
    findings file hold them, so `--correct` can tell which ask changed."""
    target = choose_asks_packet(waiting, options.packet_id)
    outcomes, notes = read_outcomes(options.outcome_words, target["asks"])
    refuse_conditional_changes(target["asks"], outcomes)
    refuse_changed_retry(state, target, outcomes, notes, correctable=False)
    target.setdefault("ask_outcomes", outcomes)
    target.setdefault("ask_notes", notes)
    return Answers(target, outcomes, notes, options.decided_by)


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
    """An asks-done call with no packet waiting: a retry of the finished call prints its result again, with the same
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


def command_asks_done(argv):
    options = asks_done_options(argv)
    if options.correct:
        return command_correct_asks(options)

    state = load_fix_state()
    waiting = waiting_ask_packets(state)
    if not waiting:
        return repeat_done_asks(state, options)

    target, outcomes, notes, decided_by = read_answers(state, options, waiting)
    asks = target["asks"]
    finding_lines = ask_finding_lines(asks, outcomes, notes)
    findings_file = write_unprinted_fix_run(state, target, finding_lines, decided_by)

    ask_counts, failures = log_fix_ask_outcomes(target, asks, outcomes, decided_by)
    summary_lines = [summary_line(target, asks, ask_counts, decided_by, failures),
                     *["- " + failure for failure in failures]]
    deviation_lines = unprinted_deviation_lines(target, asks, outcomes, notes, decided_by)
    if deviation_lines:
        summary_lines += [ADD_DEVIATIONS_LINE, *deviation_lines]

    if not failures:
        mark_packet_answered(state, target)
    save_fix_state(state)

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
