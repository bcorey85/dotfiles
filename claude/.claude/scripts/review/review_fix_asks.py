"""review_fix_asks.py: `review_fix.py asks-done`. It logs one outcome row per ask, once. When the user accepted or
modified an ask, it writes those asks to a findings file and prints the fix run that applies them: the first run's
launch flags plus `--fix`, `--iter` and `--detach`, so the loop's fix coder makes the change, a review round covers
it, and the converged hand-back earns commit credit."""
import pathlib
import shlex
import sys

import plan_format
import review_asks
import review_launch
import script_utils
from handback import PLAN_IMPACT_STATUS, is_plan_impact_ask
from review_asks import ASK_OUTCOMES, MODIFIED, REJECTED
from review_fix_state import (
    ADD_DEVIATIONS_LINE,
    ASK_LOGGER,
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
ASK_FINDINGS_NAME = "ask-findings.md"
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
            raise UsageError(f"outcome {word!r} is not one of {'|'.join(ASK_OUTCOMES)}")
        if outcome == MODIFIED and not note.strip():
            raise UsageError(f"outcome {number} is modified with no note; "
                             "write 'modified:<the user's change>' quoted as one shell word")
        outcomes.append(outcome)
        notes.append(one_line(note, None))
    return outcomes, notes


def log_fix_ask_outcomes(state, asks, outcomes, decided_by="user"):
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
            if outcome_row.new_finding_id_note:
                print(f"review-fix: {outcome_row.new_finding_id_note}", file=sys.stderr)
                ask_counts[NEW_FINDING_ID] += 1
            continue
        path, line = split_location(item.get("file_line") or "-")
        failures.append(f"{path}:{line}: {one_line(outcome_row.output, 160)}")
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


def asks_done_options(argv):
    """(outcome words, who decided, the named packet_id or None) of an asks-done call."""
    outcome_words, decided_by = script_utils.pop_option(argv, "--by")
    if decided_by is None:
        decided_by = "user"
    if not plan_format.is_ruling_by(decided_by):
        raise UsageError(f"asks-done --by needs user or session, not {decided_by!r}")

    outcome_words, packet_id = script_utils.pop_option(outcome_words, "--packet")
    if packet_id == "":
        raise UsageError("asks-done --packet needs a packet_id")
    return outcome_words, decided_by, packet_id


def ask_finding_lines(asks, outcomes, notes):
    """One findings-file item per accepted or modified ask that is not a plan impact, in the form
    review_launch.read_findings_file reads. A modified ask carries the user's change in place of the proposed one."""
    lines = []
    for item, outcome, note in zip(asks, outcomes, notes, strict=True):
        if outcome == REJECTED or is_plan_impact_ask(item):
            continue
        question = one_line(item["question"], None)
        change = one_line(item["change"], None)
        text = f"{item['file_line']} {question} Proposed change: {change}"
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
    if decided_by == "session":
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


def fix_launch_line(target, findings_file):
    """The launch line of the fix run. The fix run holds every dirty file not listed, and the first run's own
    edits are dirty, so the files it touched join the scoped files."""
    touched_paths = target.get("files_touched") or []
    relaunch_args = review_launch.relaunch_args_with_files(target["relaunch_args"], touched_paths)
    launch_args = ["--fix", str(findings_file), "--iter", str(target["iter"]), *relaunch_args, "--detach"]
    return f"{LAUNCH_COMMAND} {shlex.join(launch_args)}"


def no_record_launch_line(target, findings_file):
    """The launch line of a fix run with no launch record: `--iter`, the dispatched `--repo` and `--detach` only."""
    repo = dispatched_repo() or pathlib.Path.cwd()
    launch_args = ["--fix", str(findings_file), "--iter", str(target["iter"]), "--repo", str(repo), "--detach"]
    return f"{LAUNCH_COMMAND} {shlex.join(launch_args)}"


def unprinted_deviation_lines(target, asks, outcomes, notes, decided_by):
    """Returns the plan-deviation lines once per packet: a retry after a logging failure gets none."""
    if target.get("asks_deviations_printed"):
        return []
    deviation_lines = accepted_ask_deviation_lines(asks, outcomes, notes, decided_by)
    if deviation_lines:
        target["asks_deviations_printed"] = True
    return deviation_lines


def write_unprinted_fix_run(target, finding_lines):
    """Writes the findings file for a fix run not yet printed and returns its path, else None. The write comes
    before the latch: a failed write leaves the state unlatched, so a retry prints the run."""
    if not finding_lines or target.get("asks_redispatched"):
        return None
    findings_file = write_findings_file(finding_lines)
    target["asks_redispatched"] = True
    if not target.get("relaunch_args"):
        target["asks_launch_line"] = no_record_launch_line(target, findings_file)
        return findings_file
    target["asks_launch_line"] = fix_launch_line(target, findings_file)
    return findings_file


def print_done_again(state):
    """A repeat asks-done with every ask logged. A stored fix run is printed again: the first call may have been
    cut off before its launch line was run."""
    done_line = "The ask outcomes were already logged."
    launch_line = state.get("last_asks_launch_line")
    if not launch_line:
        return print_action("done", done_line, "Run nothing more.")
    return print_action("done", done_line, PRINTED_RUN_LINE, launch_line)


def command_asks_done(argv):
    state = load_fix_state()
    waiting = waiting_ask_packets(state)
    if not waiting:
        if state.get("stage") == "done" and state.get("asks"):
            return print_done_again(state)
        raise UsageError("no asks are waiting. `asks-done` follows a packet that carried ask[] entries.")

    outcome_words, decided_by, packet_id = asks_done_options(argv)
    target = choose_asks_packet(waiting, packet_id)
    asks = target["asks"]
    outcomes, notes = read_outcomes(outcome_words, asks)

    finding_lines = ask_finding_lines(asks, outcomes, notes)
    findings_file = write_unprinted_fix_run(target, finding_lines)

    ask_counts, failures = log_fix_ask_outcomes(target, asks, outcomes, decided_by)
    summary_lines = [summary_line(target, asks, ask_counts, decided_by, failures),
                     *["- " + failure for failure in failures]]
    deviation_lines = unprinted_deviation_lines(target, asks, outcomes, notes, decided_by)
    if deviation_lines:
        summary_lines += [ADD_DEVIATIONS_LINE, *deviation_lines]

    if not failures and target is state:
        state["stage"] = "done"
    if not failures and target is not state:
        state["waiting_packets"] = [kept for kept in state["waiting_packets"] if kept is not target]
    if not failures:
        state["last_asks_launch_line"] = target.get("asks_launch_line")
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
