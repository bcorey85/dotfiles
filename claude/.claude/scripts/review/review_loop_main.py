"""review_loop_main.py: the entry of the scripted review loop: the request, the loop's build, the run, the packet and
the exit code. review_loop_script.py holds the graph and the module doc, and calls `main` when it runs as a script."""

import argparse
import contextlib
import os
import pathlib
import signal
import sys
import typing

import full_check
import full_check_gate
import handback
import plan_format
import review_loop_held
import review_loop_script
import script_utils
from review_loop_calls import CALLS, LIVE_CHILDREN, PARENT_SESSION, now
from review_loop_packet import crash_outcome, packet_message, write_handback_rows, write_usage_row
from review_loop_plan import ChangeUnderReview
from review_loop_prompt_file import (
    BASE_KEY,
    FILES_KEY,
    HELD_FILES_KEY,
    NO_REVIEW_KEY,
    REVIEWER_MODEL_KEY,
    REVIEWERS_HEADLESS,
    REVIEWERS_MAIN,
    YES,
    header_iter,
    header_list,
    read_findings,
    read_prompt,
    reviewer_brief,
)
from review_loop_script import (
    ROUND_BUDGET,
    SKILLS,
    ChangeRemovedError,
    LaterPhaseEditError,
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


def build_loop(request):
    """The LoopRun for one request, with the settings its prompt header gives. Returns (loop, check_command)."""
    header, handoff, repo = request.header, request.handoff, request.repo
    brief = reviewer_brief(header, handoff)
    gate_env = plan_format.gate_env_words_in(handoff)
    loop = LoopRun(repo, request.out, brief, gate_env, request.progress, header.get("plan", ""))
    loop.reviewers = request.reviewers
    loop.later_phase_files = later_phase_files(header)
    loop.guidance = header.get("guidance", "")
    loop.resolved_texts = plan_format.resolved_plan_texts(handoff)
    loop.change = ChangeUnderReview(repo)

    log_call(repo, [str(SKILLS / "review-scope"), f"caller={header.get('caller', 'code')}"])
    found_command = full_check.configured_check_command(repo)
    plan = header.get("plan")
    plan_on_disk = plan if plan and (pathlib.Path(repo) / plan).is_file() else None
    check_command, loop.expected_red = full_check.phase_check(repo, found_command, plan_on_disk, header.get("phase"))
    if plan_on_disk:
        plan_lines = (pathlib.Path(repo) / plan_on_disk).read_text().splitlines()
        loop.test_strategy = plan_format.test_strategy_section(plan_lines)

    loop.gates_every_run = request.gates_every_run
    loop.reviewer_model = header.get(REVIEWER_MODEL_KEY, "")
    loop.review_base = header.get(BASE_KEY, "")
    loop.only_files = header_list(header, FILES_KEY)
    caller_held = header_list(header, HELD_FILES_KEY)
    loop.held_files = review_loop_held.run_held_files(repo, caller_held, loop.only_files)
    loop.iter_count = min(header_iter(header), ROUND_BUDGET - 1)
    request.progress["iter"] = loop.iter_count
    return loop, check_command


def tally_actioned(loop):
    """Sets the metrics tallies of fixed and skipped findings from the run rows and the findings fixed outside them."""
    every_actioned = []
    for row in loop.run_rows:
        every_actioned += [finding["actioned"] for finding in row["findings"]]
    loop.tallies["fixed"] = every_actioned.count("fixed") + loop.check_fixed
    loop.tallies["skipped_fp"] = every_actioned.count("skipped_fp") + loop.given_skipped


def run_loop(request):
    """Walks the graph. Returns the outcome mapping. `request.progress` holds what a crash still reports: iter, fixed
    and files_touched, updated in place as the loop goes. `request.reviewers` says who runs the reviewers."""
    header = request.header
    structure_pass_skipped = header.get("structure-pass") == "skip"
    scope_fields = telemetry_scope_fields(header, header.get("caller", "code"))
    loop, check_command = build_loop(request)
    try:
        first_pass(loop, read_findings(header), header.get(NO_REVIEW_KEY) == YES, structure_pass_skipped)
        walk(loop, check_command, request.gate_commands)
    except LaterPhaseEditError as error:
        loop.stop("critical-blocker", [str(error)])
    except ChangeRemovedError as error:
        loop.stop(handback.FIX_REMOVED_CHANGE, [str(error)])

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
    PARENT_SESSION["label"] = script_utils.session_display_name(args.session) or f"session {args.session}"
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
