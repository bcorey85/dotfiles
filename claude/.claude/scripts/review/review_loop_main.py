"""review_loop_main.py: the entry of the scripted review loop: the request, the loop's build, the run, the packet and
the exit code. review_loop_script.py holds the graph and the module doc, and calls `main` when it runs as a script."""

import argparse
import contextlib
import os
import pathlib
import signal
import sys
import typing

import check_parts
import full_check
import full_check_gate
import handback
import handback_store
import plan_format
import review_loop_held
import review_loop_partial_fix
import review_loop_script
import script_utils
import session_registry
from finding_record import parse_finding
from review_loop_calls import CALLS, LIVE_CHILDREN, PARENT_SESSION, now
from review_loop_named_tests import NamedTestRemovedError
from review_loop_packet import crash_outcome, packet_message, write_handback_rows, write_usage_row
from review_loop_pass_checks import ChangeRemovedError, LaterPhaseEditError
from review_loop_plan import ChangeUnderReview
from review_loop_prompt_file import (
    BASE_KEY,
    CODER_MODEL_KEY,
    FILES_KEY,
    HELD_FILES_KEY,
    NO_REVIEW_KEY,
    PLAN_KEY,
    REVIEWER_MODEL_KEY,
    REVIEWERS_HEADLESS,
    REVIEWERS_MAIN,
    RULED_OUT_FILES_KEY,
    SESSION_RULED_HEADER_KEY,
    USER_RULED_AT_KEY,
    USER_RULED_HEADER_KEY,
    YES,
    header_adopted,
    header_fix_rounds,
    header_held_by,
    header_iter,
    header_list,
    header_post_cap_passes,
    header_ruled,
    read_findings,
    read_prompt,
    reviewer_brief,
)
from review_loop_ruled import adopted_rulings, rejected_ask_questions, rejected_ask_records
from review_loop_ruling_check import RulingBrokenError, RulingCheckFaultError
from review_loop_scoped_tests import test_commands_of
from review_loop_script import (
    ROUND_BUDGET,
    SKILLS,
    CoderFailedError,
    LoopRun,
    TelemetryRun,
    first_pass,
    log_call,
    walk,
    write_telemetry,
)


class LoopRequest(typing.NamedTuple):
    """What one run of the loop is given: the repo, the state folder, the caller's prompt file and its settings."""

    repo: str
    out: pathlib.Path
    session: str
    header: dict
    handoff: str
    progress: dict
    gate_commands: typing.Sequence = ()
    reviewers: str = REVIEWERS_HEADLESS
    gates_every_run: bool = False


def telemetry_scope_fields(header, caller):
    """The `scope=` fields every telemetry row of this run carries."""
    if caller != "code":
        return ["scope=standalone"]
    if header.get("phase"):
        return ["scope=phase", f"phase={header['phase']}"]
    return ["scope=phase"]


def later_phase_files(header):
    """The set of files the plan gives to a later phase, from the prompt header's comma-separated list."""
    listed = header.get("later-phase files", "")
    names = listed.split(", ")
    return set(filter(None, names))


def default_check_could_not_run(session, repo):
    """True when the session's last hand-back for this repo stopped as a setup fault, or its full check was an
    environment gap or was itself an overridden run: the configured full check could not run here, so a `--test`
    command given now stands in for it. A previous hand-back that does not parse is not one of these."""
    previous = handback_store.latest_for_repo(session, repo)["handback"]
    if not previous:
        return False
    if previous.get("status") == handback.SETUP_FAULT_STATUS:
        return True
    if previous.get("status") == handback.INVALID_STATUS:
        return False
    try:
        packet = handback.load(previous["message"])
    except handback.PacketError:
        return False
    return packet["check_overridden"] or full_check.is_environment_gap_result(packet["full_check"])


def build_loop(request):
    """The LoopRun for one request, with the settings its prompt header gives. Returns (loop, check_command)."""
    header, handoff, repo = request.header, request.handoff, request.repo
    brief = reviewer_brief(header, handoff, repo)
    gate_env = plan_format.gate_env_words_in(handoff)
    loop = LoopRun(repo, request.out, brief, gate_env, request.progress, header.get(PLAN_KEY, ""))
    loop.reviewers = request.reviewers
    loop.later_phase_files = later_phase_files(header)
    loop.guidance = header.get("guidance", "")
    loop.resolved_texts = plan_format.resolved_plan_texts(handoff)
    loop.change = ChangeUnderReview(repo)
    loop.rejected_asks = rejected_ask_records(request.session, repo)
    loop.rejected_questions = rejected_ask_questions(request.session, repo)

    log_call(repo, [str(SKILLS / "review-scope"), f"caller={header.get('caller', 'code')}"])
    found_command = full_check.configured_check_command(repo)
    test_commands = test_commands_of(request.gate_commands)
    loop.check_overridden = bool(test_commands) and request.gates_every_run and default_check_could_not_run(
        request.session, repo)
    if loop.check_overridden:
        test_parts = [(f"test-{index}", [command]) for index, command in enumerate(test_commands, 1)]
        found_command = check_parts.join_parts(test_parts)
    plan = header.get(PLAN_KEY)
    plan_on_disk = plan if plan and (pathlib.Path(repo) / plan).is_file() else None
    loop.plan_on_disk, loop.phase = plan_on_disk, header.get("phase")
    check_command, loop.expected_red = full_check.phase_check(repo, found_command, plan_on_disk, loop.phase)
    if plan_on_disk:
        plan_lines = (pathlib.Path(repo) / plan_on_disk).read_text().splitlines()
        loop.test_strategy = plan_format.test_strategy_section(plan_lines)

    loop.gates_every_run = request.gates_every_run
    loop.gate_commands = list(request.gate_commands)
    loop.reviewer_model = header.get(REVIEWER_MODEL_KEY, "")
    loop.coder_model = header.get(CODER_MODEL_KEY, "")
    loop.review_base = header.get(BASE_KEY, "")
    loop.only_files = header_list(header, FILES_KEY)
    caller_held = header_list(header, HELD_FILES_KEY)
    loop.held_files = review_loop_held.run_held_files(repo, caller_held, loop.only_files)
    loop.ruled_out = set(header_list(header, RULED_OUT_FILES_KEY))
    loop.held_holders = review_loop_held.caller_holders(caller_held, header_held_by(header))
    loop.held_holders.update(review_loop_held.implicit_holders(
        repo, loop.held_files, loop.held_holders, loop.only_files, request.session))
    loop.iter_count = min(header_iter(header), ROUND_BUDGET - 1)
    request.progress["iter"] = loop.iter_count
    loop.fix_rounds = min(header_fix_rounds(header), ROUND_BUDGET)
    loop.post_cap_passes = tuple(header_post_cap_passes(header))
    return loop, check_command


def tally_actioned(loop):
    """Sets the metrics tallies of fixed and skipped findings from the run rows and the findings fixed outside them."""
    every_actioned = []
    for row in loop.run_rows:
        every_actioned += [finding["actioned"] for finding in row["findings"]]
    loop.tallies["fixed"] = every_actioned.count("fixed") + loop.check_fixed
    loop.tallies["skipped_fp"] = every_actioned.count("skipped_fp") + loop.given_skipped


# The running loop and its repo, so the stop signal can save the record held only in memory.
RUNNING = {"loop": None, "repo": None}


def save_pending_record(repo, pending, in_flight):
    """Saves the partial-fix record. A save failure is printed to stderr; it is raised only when no other exception
    is in flight, so it never replaces the real crash cause."""
    try:
        review_loop_partial_fix.save_pending(repo, pending, now())
    except OSError as error:
        print(f"review-loop-script: could not save the partial-fix record: {error}", file=sys.stderr)
        if not in_flight:
            raise


def run_loop(request):
    """Walks the graph. Returns the outcome mapping. `request.progress` holds what a crash still reports: iter, fixed
    and files_touched, updated in place as the loop goes. `request.reviewers` says who runs the reviewers."""
    header = request.header
    structure_pass_skipped = header.get("structure-pass") == "skip"
    scope_fields = telemetry_scope_fields(header, header.get("caller", "code"))
    loop, check_command = build_loop(request)
    RUNNING.update(loop=loop, repo=request.repo)
    try:
        header_findings = read_findings(header)
        saved = review_loop_partial_fix.saved_findings(request.repo)
        loop.saved_record_texts = saved
        carried = review_loop_partial_fix.saved_findings_not_in_header(saved, header_findings)
        # Carried findings add a fix-first pass but never cost the run its structure pass.
        structure_pass_skipped = structure_pass_skipped or bool(header_findings)
        findings = [*header_findings, *carried]
        loop.user_ruled = header_ruled(header, header_findings, USER_RULED_HEADER_KEY)
        loop.user_ruled_at = header.get(USER_RULED_AT_KEY, "")
        loop.adopted = adopted_rulings(header_adopted(header, header_findings))
        loop.session_id = request.session
        loop.session_ruled = header_ruled(header, header_findings, SESSION_RULED_HEADER_KEY)
        loop.resume_approval_asks([parse_finding(text) for text in findings])
        first_pass(loop, findings, header.get(NO_REVIEW_KEY) == YES, structure_pass_skipped)
        walk(loop, check_command, request.gate_commands)
    except (LaterPhaseEditError, CoderFailedError, NamedTestRemovedError, RulingBrokenError,
            RulingCheckFaultError) as error:
        loop.stop("critical-blocker", [str(error)])
    except ChangeRemovedError as error:
        loop.stop(handback.FIX_REMOVED_CHANGE, [str(error)])
    except plan_format.PlanFormatError as error:
        # The message names the plan file, the line and the expected form of the standing ruling.
        loop.stop("critical-blocker", [f"the plan's standing ruling does not parse: {error}"])
    except review_loop_partial_fix.SavedRecordError as error:
        # The message names the saved record's file to delete.
        loop.stop("critical-blocker", [str(error)])
    finally:
        # One write per run, even when an unlisted error ends it: a pass that died or settled the saved record only
        # sets what the file is to hold.
        save_pending_record(request.repo, loop.pending_record, in_flight=sys.exc_info()[0] is not None)

    if request.gates_every_run and loop.status != "converged" and not loop.scoped_tests:
        loop.scoped_tests = full_check.SCOPED_NOT_RUN_STOPPED.format(status=loop.status)
    tally_actioned(loop)
    run = TelemetryRun(request.session, header["lane"], scope_fields, loop.iter_count, loop.tallies, loop.run_rows,
                       request.out)
    ask_ids, ask_rows = write_telemetry(request.repo, run)
    return loop.outcome(ask_ids, ask_rows)


def stop_on_sigterm(_signal_number, _frame):
    """The stop signal of a caller stopping the loop: kill the process group of every claude call
    that is running and remove the base run's worktree, then exit without a packet."""
    for pid in list(LIVE_CHILDREN):
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(pid, signal.SIGKILL)
    full_check_gate.remove_live_base_trees()
    if RUNNING["loop"] is not None:
        save_pending_record(RUNNING["repo"], RUNNING["loop"].pending_record, in_flight=True)
    os._exit(128 + signal.SIGTERM)


def parse_review_loop_arguments(argv):
    parser = argparse.ArgumentParser(description=review_loop_script.__doc__.splitlines()[0])
    parser.add_argument("repo")
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--gate-command", action="append", default=[])
    parser.add_argument("--reviewers", choices=(REVIEWERS_HEADLESS, REVIEWERS_MAIN), default=REVIEWERS_HEADLESS)
    parser.add_argument("--gates-every-run", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_review_loop_arguments(argv)
    signal.signal(signal.SIGTERM, stop_on_sigterm)
    PARENT_SESSION["label"] = session_registry.session_display_name(args.session) or f"session {args.session}"
    repo = str(pathlib.Path(args.repo).resolve())
    out = pathlib.Path(args.state_dir) / "loop-script" / args.agent_id
    out.mkdir(parents=True, exist_ok=True)
    started = now()
    progress = {"iter": 0, "fixed": [], "files_touched": set()}

    exit_code = 0
    outcome = None
    try:
        header, handoff = read_prompt(args.prompt_file)
        request = LoopRequest(repo, out, args.session, header, handoff, progress, args.gate_command, args.reviewers,
                              args.gates_every_run)
        outcome = run_loop(request)
        message = packet_message(outcome)
        handback.load(message)
    except handback.PacketError as error:
        problems = "; ".join(error.problems)
        print(f"review-loop-script: the packet does not parse: {problems}", file=sys.stderr)
        reason = f"the review loop packet failed validation ({problems}); call log: {out / 'calls.jsonl'}"
        outcome = {**crash_outcome(progress, reason), "ask_rows": outcome["ask_rows"]}
        message = packet_message(outcome)
        exit_code = 1
    except Exception as error:
        print(f"review-loop-script: {type(error).__name__}: {error}", file=sys.stderr)
        reason = script_utils.one_line(f"the review loop script failed with {type(error).__name__}: {error}; "
                                       f"call log: {out / 'calls.jsonl'}", limit=None)
        outcome = crash_outcome(progress, reason)
        message = packet_message(outcome)
        exit_code = 1

    status = handback.load(message)["status"]
    (out / "packet.txt").write_text(message + "\n")
    write_handback_rows(args, message, status, outcome["ask_rows"], outcome["unreviewed_fix"])
    write_usage_row(repo, started, CALLS)
    print(message)
    return exit_code
