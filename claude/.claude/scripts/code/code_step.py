#!/usr/bin/env python3
"""code_step.py: the routing of /code as a script. The forked Sonnet subagent of /code runs one verb, reads its
ACTION lines, does exactly that, and runs the next verb. The script builds every prompt and every argument.

  code_step.py start [<plan>] [+fast|+deep] [--phase <id>] [--restart] [<run notes>]
                                                next phase of the plan (or the named one): checks, gate, packet, the
                                                exact coder dispatch. `start --help` prints usage. --restart drops an
                                                unfinished run first; `--restart <text>` over a saved plan with open
                                                phases makes the text run notes (use --task for planless work).
  code_step.py start --task "<text>"           planless work: the coder dispatch without gate or packet
  code_step.py start --task-file <path>        the same, with the text read from a file
  code_step.py start --repo <path> ...         run in that checkout, not the current directory (a `Repo: <path>` first
                                                line in the task file does the same)
  code_step.py resume                           do the next step of the saved run, whatever stage or stop it is in
  code_step.py resume <text>                    the answer to a stopped coder; with no run open, the same as start
  code_step.py <verb> --help                    print that verb's usage and change nothing (code_step_usage)
  code_step.py decide <adopt|keep> --by <user|session> --ruling "<the decision in one line>"
                                                only --by user is the user's own word: a session ruling never changes
                                                a criterion
  code_step.py decide discuss                   ask the user how to rule when the code and the plan disagree; records
                                                nothing
  code_step.py asks-done [--repo <path>] [--by <user|session>] [--also "<text>"] <outcome>...
                                                --repo: the checkout of the run, when the shell is in none of them;
                                                log the answer to each ask[] entry, then run the phase gates;
                                                --by session when the session ruled itself, default user;
                                                --also: other work for the coder, kept even if every ask is rejected
  code_step.py correct-ruling [--repo <path>] [--by <user|session>] [--also "<text>"] <outcome>...
                                                --repo: as for asks-done;
                                                while the asks coder runs: save corrected rulings; a correction coder
                                                applies them when the asks coder reports, before the review
  code_step.py skill-done <pass|fail> [--evidence "<text>"]... [--finding "<text>"]...
                                                a closing phase's skill returned: mark it done (pass) or stop (fail);
                                                at pass, give one --evidence per open Success Criteria item and the
                                                script writes it into the plan
  code_step.py verify                           re-run the phase gates after a failed Automated Verification was fixed
  code_step.py review-again                     dispatch the review loop again on the same diff, after a stop that
                                                names it (unreadable packet, cap, false-clean, tool fault,
                                                critical blocker, setup fault)
  code_step.py tick <phase id>                  mark a phase done that the user finished outside /code
  code_step.py abort                            end the open run on purpose: settle its criteria copy, clear its gate
                                                and texts, archive state.json as aborted-<UTC time>.json; the working
                                                tree stays as it is
  code_step.py guide "<text>"                   record the main session's guidance in the open run; every later coder
                                                and review dispatch carries it (code_guidance). It changes neither the
                                                task nor the plan
  code_step.py hook                             PreToolUse hook on SubagentHandback: deny the fork's hand-back while a
                                                dispatched agent is still out
  code_step.py log-hook                         PostToolUse hook on Agent|SubagentHandback|SendMessage: log launch,
                                                hand-back and resume events of the run
  code_step.py dispatch-hook                    PreToolUse hook on Agent: deny a coder or review-loop launch whose
                                                prompt lacks the saved dispatch prompt, or a repeat launch of a coder
  code_step.py launch-hook                      PreToolUse hook on Skill: deny a /code resume of a run stopped on its
                                                Automated Verification (a failed command or an item that could not be
                                                run), naming the fix and then verify
  code_step.py stop-hook                        SubagentStop hook: keep the /code fork from stopping while a dispatch
                                                is open
  code_step.py plan-hook                        PostToolUse hook on Edit|Write: reject a plan edit that does not parse
  code_step.py status                           print the saved state

One coder runs per phase. The current skill's two parallel coders for deliverables that share no file are dropped by
design.
Run `start` from the repo root; every later verb and `status` goes on in the checkout of the session's open run.
State lives in <git dir>/code-step/. Env CODE_STEP_CLAUDE_DIR overrides the toolkit folder;
CODE_STEP_NVIM_JUMP overrides the nvim-jump command.
Each run also keeps <git dir>/code-step/runs/<run id>/events.jsonl and one prompt-<dispatch id>.txt per dispatch. The
hooks write only that log; the verbs read it and write state.json.

The code is split in files that import one way: code_step_state (the run's record), code_step_routes (the route table
and stage facts), code_step_core (state, event log, hand-back matcher, output), code_step_verification (Automated
Verification reader and runner), code_step_boundary (criteria guard, phase boundary, tick and verify),
code_step_closing (skill-done), code_step_hooks, code_step_gates (gate commands), code_step_start (the start verb),
code_step_report (reading a coder report), code_step_review (plan-impact modal, plan-edit dispatch, review dispatch,
review packet, asks), code_step_asks (the asks route's words: ask listing, pre-set outcome, asks-done arguments, asks
coder prompt, prior issues; ask ids and outcome rows come from review/review_asks.py), code_step_usage (usage text and
the leading-dash check of `resume`) and this file."""
import contextlib
import fcntl
import json
import os
import pathlib
import sys
import time

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import coder_gate
import plan_format
import script_utils
from code_guidance import record_guidance
from code_step_asks import prior_issues
from code_step_boundary import (
    command_tick,
    command_verify,
    finish_phase,
    settle_criteria_guard,
)
from code_step_closing import command_skill_done_with_question
from code_step_core import (
    CODER,
    RESUME_VERB,
    REVIEW_AGAIN_INVOKE,
    StateFileError,
    ask_user,
    awaited_agent_id,
    awaited_handback,
    branch_label,
    carried_start_words,
    changed_since_baseline,
    clear_question,
    clear_say,
    coder_changed_files,
    current_phase_text,
    dispatch_since,
    drop_state,
    emit,
    file_hashes,
    guarded_verb_runs,
    head_commit,
    head_left_phase_start,
    is_run_open,
    load_state,
    newest_later_phase_deny_reason,
    own_phase_text,
    phase_coder_reports,
    read_events,
    refuse,
    repo_root_or_exit,
    restart_instruction,
    resume_run_repos,
    review_script_running,
    run_coder_gate,
    save_state,
    say,
    script_command,
    sent_message_since,
    session_pin,
    set_stop,
    snapshot_part,
    stale_phase_reason,
    state_dir,
    state_text,
    stop_kind,
    stop_review_script,
    stop_with_question,
    take_handback,
    timed_command,
    verb_transaction,
    wait_for_handback,
)
from code_step_hooks import (
    command_dispatch_hook,
    command_hook,
    command_launch_hook,
    command_log_hook,
    command_plan_hook,
    command_say_hook,
    command_stop_hook,
    expected_red_failure,
    outside_scope_flags,
)
from code_step_report import (
    behavior_lines,
    coder_message_without_gate_stamp,
    every_accepted_ask_already_done,
    first_plan_impact,
    gate_results,
    impact_replaced,
    open_questions,
    recommends_eng_spec,
    resolve_report_paths,
    tests_run_text,
    why_by_file,
)
from code_step_review import (
    GO_ON_REFUSAL_VERBS,
    VERB_REFUSALS,
    ask_the_user,
    command_after_plan_edit,
    command_after_review,
    command_asks_done,
    command_correct_ruling,
    command_decide,
    command_review_again,
    dispatch_correction_coder,
    emit_plan_impact_modal,
    emit_review_dispatch,
)
from code_step_review_stops import blocker_stop_next_step, blocker_stop_text, left_findings_open
from code_step_routes import GUARDED_VERBS, ROUTES, STAGE_FACTS, STALE_PHASE_STEP, StageFact, resume_step, state_key
from code_step_start import (
    command_start,
    emit_closing_skill,
    phase_label,
    resume_text_refusal,
    stopped_run_restart_instruction,
)
from code_step_state import Stage, StopKind
from code_step_usage import VERB_USAGES, check_verb_arguments, print_usage_if_asked
from code_step_verification import verification_format_failure

# These verbs open a new /code run after the user answered. The last run's say.md text was already handed back.
VERBS_THAT_CLEAR_SAY = ("decide", "asks-done", "verify", "review-again")
# A correction or guidance arrives while a run may sit stopped on a coder's report: question.md still names that stop.
VERBS_THAT_KEEP_QUESTION = ("correct-ruling", "guide")
NO_CODER_REPORT = ("No coder report was saved. The log-hook (code_step.py log-hook) is not installed or the coder "
                   "never handed back. Tell the user.")


# ---------- plan check ----------

def command_plan(args):
    # `plan check --final <path>` also fails a spec whose criteria file was never written.
    final = args[1:2] == ["--final"] and args[0] == "check"
    path_args = args[2:] if final else args[1:]
    if not path_args or args[0] not in ("check", "parse"):
        sys.exit(VERB_USAGES["plan"])
    plan_path = path_args[0]

    plan_lines = pathlib.Path(plan_path).read_text().splitlines()
    plan = plan_format.parse_plan_with_closing_phases(plan_lines)
    if args[0] == "parse":
        return print(json.dumps(plan, indent=1))
    for row in plan_format.plan_failure_rows(plan, plan_path):
        print(row)
    manual_failure = plan_format.manual_format_failure(plan_lines, plan_path)
    if manual_failure:
        print(manual_failure)
    # From a repo subdirectory the checks resolve against the repo root; outside a repo against the current directory.
    repo_dir = script_utils.repo_root(os.getcwd()) or pathlib.Path.cwd()
    verification_failure = verification_format_failure(plan_lines, plan_path, repo_dir, plan["entries"])
    if verification_failure:
        print(verification_failure)

    red_failure = expected_red_failure(plan_lines, plan_path, repo_dir)
    if red_failure:
        print(red_failure)
    for row in plan_format.plain_verification_item_warnings(plan_lines, plan_path):
        print(row)
    ac_failures = plan_format.spec_ac_failures(pathlib.Path(plan_path))
    for row in ac_failures:
        print(row)
    criteria_failure = plan_format.missing_criteria_failure(pathlib.Path(plan_path)) if final else None
    if criteria_failure:
        print(criteria_failure)
    failed = (plan["failures"] or manual_failure or verification_failure or red_failure or ac_failures
              or criteria_failure)
    sys.exit(1 if failed else 0)


# ---------- coder hand-back ----------

DOCS_SUFFIXES = (".md", ".mdx", ".rst", ".txt")


def asks_coder_changed_files(changed_now, asks_baseline):
    # The files whose hash differs between the snapshot taken at the asks-coder dispatch and now, new and deleted
    # included.
    names = set(changed_now) | set(asks_baseline)
    return sorted(name for name in names if changed_now.get(name) != asks_baseline.get(name))


def finish_without_review(repo_dir, state, changed_files, coder_stage, say_text):
    # No review has anything to cover: run the phase's verification commands and tick, as after a clean review.
    state.files = changed_files
    state.coder_stage = coder_stage
    state.stage = "review"
    state.correction_coder = None
    save_state(repo_dir, state)
    say(repo_dir, say_text)
    return finish_phase(repo_dir, state)


def coder_flagged(state, gate, report, is_ask_fix):
    # The report's open points, with the hand-back gate's cap, its command errors and the flags an asks-coder
    # inherits. A command error is no code failure, so it is flagged apart from the cap.
    flagged = list(state.flagged) if is_ask_fix else []
    coders = (gate or {"coders": {}})["coders"].values()
    for coder in coders:
        coder_commands = coder.get("commands", {})
        if coder["result"] == "cap":
            failed_commands = script_utils.details_with_outcome(coder_commands, coder_gate.FAILED)
            flagged.append("hand-back gate cap: " + ", ".join(failed_commands) + " still failing after 3 denials")

        for command, line in script_utils.details_with_outcome(coder_commands, coder_gate.COMMAND_ERROR).items():
            flagged.append(f"hand-back gate command error, not a code failure: `{command}` names a missing path "
                           f"({line})")
    return flagged + open_questions(report)


def unreviewable_outcome(repo_dir, state, report, changed_files, changed_now):
    # "converged" when the asks coder changed nothing and named, for each confirmed ask, the file:line that already
    # does it or the check that passed; "recommended-eng-spec" for a report whose marker line recommends /eng-spec;
    # "undone" when a correction coder put the tree back where the asks round began and no ask stays accepted;
    # "no-change" for a report with no reviewable change (a failed edit, a blocked hook, a question); else None.
    is_ask_fix = state.stage == Stage.ASKS_CODER
    asks_coder_changed_nothing = is_ask_fix and changed_now == snapshot_part(state, "asks")
    escalates = recommends_eng_spec(report)
    report_raises_blocker = escalates or bool(first_plan_impact([report])) or bool(open_questions(report))
    if asks_coder_changed_nothing and not report_raises_blocker and every_accepted_ask_already_done(
            repo_dir, state, report):
        return "converged"

    nothing_left_to_apply = not state.accepted_asks and not state.asks_also
    if asks_coder_changed_nothing and not report_raises_blocker and state.correction_coder \
            and nothing_left_to_apply:
        return "undone"
    if escalates:
        return "recommended-eng-spec"
    if not changed_files or asks_coder_changed_nothing:
        return "no-change"
    return None


CODER_REPORT_STOP_LINES = 6
# The unreviewable outcomes that stop the run on the coder's report, and the words that finish "The coder ...".
CODER_STOP_CAUSES = {"no-change": "produced no reviewable change", "recommended-eng-spec": "recommended /eng-spec"}


def stop_on_coder_report(repo_dir, state, report, agent_id, cause_text, restart_only=False):
    # The run stops on the coder's report: the user answers it, and the coder resumed with SendMessage goes on.
    # cause_text finishes the sentence "The coder ...". restart_only names the restart as the one way out, for a
    # stop where the coder cannot go on.
    set_stop(state, StopKind.CODER_RESUMABLE, agent_id=agent_id or "unknown", coder_stage=state.stage)
    state.dispatch_at = None
    save_state(repo_dir, state)
    tick_text = (f" If the user says Phase {state.phase} is already done, invoke Skill code with `tick "
                f"{state.phase}`; do that only on the user's word." if state.plan and state.phase
                else "")
    resume_text = (" If the user answers the coder's blocker, resume that coder with SendMessage, then run "
                  f"{timed_command()}.")
    report_lines = [line for line in report.splitlines() if line.strip()][:CODER_REPORT_STOP_LINES]
    if state.pending_correction is not None:
        report_lines.append("A corrected ruling is saved; a correction coder applies it when the asks coder's work "
                            "goes on.")
    next_step = (f"if the user answers the coder's blocker, resume that coder with SendMessage, then run "
                 f"`{script_command(RESUME_VERB)}`. To dispatch a new coder for the phase, "
                 f"{restart_instruction(state)}.")
    if restart_only:
        resume_text = f" To dispatch a new coder for the phase, {restart_instruction(state)}."
        next_step = f"to dispatch a new coder for the phase, {restart_instruction(state)}."
    stop_with_question(
        repo_dir, f"the coder {cause_text}.", report_lines, next_step,
        f"The coder {cause_text}. Do not dispatch a "
        "review. Do not mark the phase done." + tick_text + resume_text
        + " Relay the coder's report to the user:", report)


def record_coder_report(repo_dir, state, report, gate, changed_files, asks_changed_files=None):
    # Saves what the review needs from a reviewable report: behavior, why notes, tests run and files. The summary
    # replaces the earlier notes of asks_changed_files (the files the asks coder changed; the files it wrote notes
    # for when no asks snapshot exists), while changed_files is the review scope. A correction coder replaces only
    # the paths in its own why_groups.
    coder_stage = state.stage
    is_ask_fix = coder_stage == Stage.ASKS_CODER
    behavior = behavior_lines(report)
    why_groups = resolve_report_paths(why_by_file(report), changed_files)
    tests_run = tests_run_text(gate, state)
    if is_ask_fix:
        # The ask-fix coder's behavior stays off the phase's own behavior (its Implemented line and Behavior delta).
        state.ask_rounds = [*state.ask_rounds, behavior]
        behavior = list(state.behavior or [])
        # The summary shows the asks coder's notes for the files it changed and the earlier notes for the rest. The
        # reviewer's notes (state.why) keep the phase coder's notes for a changed file ahead of the asks coder's.
        earlier_summary_why = state.summary_why if state.summary_why is not None else state.why
        is_correction = bool(state.correction_coder)
        state.correction_coder = None
        replaced_paths = why_groups if is_correction or asks_changed_files is None else asks_changed_files
        kept_earlier_why = {path: notes for path, notes in earlier_summary_why.items() if path not in replaced_paths}
        state.summary_why = {**kept_earlier_why, **why_groups}
        for path, notes in state.why.items():
            if path in changed_files:
                why_groups[path] = notes + why_groups.get(path, [])
        tests_run = state.tests_run + "; ask-fix coder -> ran its own checks"
        state.iter = 0
        state.spec_iter = 0
        state.prior_issues = prior_issues(state.accepted_asks)
    else:
        state.summary_why = None
    state.behavior = behavior
    state.exception = bool(state.flagged)
    state.files = changed_files
    state.why = why_groups
    state.tests_run = tests_run
    state.coder_stage = coder_stage


def stage_plan_impact(repo_dir, state, coder_stage):
    # The first PLAN-IMPACT block in any hand-back, or attempt to hand back, of the coders this run dispatched at this
    # stage. A hand-back that a gate denied still counts: the coder may send only the fix on its retry. The block the
    # run already stopped on is skipped, so a resumed coder's next hand-back is not read as that block again.
    messages = [coder_message_without_gate_stamp(message)
                for report in phase_coder_reports(repo_dir, state) if report["stage"] == coder_stage
                for message in report["attempts"] + report["messages"]]
    return first_plan_impact(messages, state.handled_impacts)


def stop_when_head_left_base(repo_dir, state, report, handback):
    base_head = state.base_head
    if not head_left_phase_start(repo_dir, base_head):
        return False

    head = head_commit(repo_dir) or "unreadable"
    stop_on_coder_report(
        repo_dir, state, report, handback.get("agent_id"),
        f"handed back when HEAD {head} does not descend from, or git cannot read, the phase's start commit "
        f"{base_head} (a rebase or reset, or a git failure), so the phase's own changes cannot be told apart",
        restart_only=True)
    return True


def coder_impact_stop_cause(impact):
    # A coder's block names its cause. A report that says PLAN-IMPACT: yes with no block to read has none to name, and
    # goes to the user's modal. A block about a code-step hook or gate (`TOOLKIT_WORD`) that names no plan step is a
    # toolkit fault, whatever its cause line says.
    if plan_format.names_only_toolkit(impact):
        return plan_format.cause_stop("toolkit")
    return plan_format.plan_impact_stop_cause(impact, cause_required=True)


def stop_on_plan_impact_cause(repo_dir, state, handback, impact, stop_cause):
    # The stop leaves the stage at the coder; the block is marked so the resumed coder's hand-back is not stopped on
    # it again.
    state.handled_impacts = [*(state.handled_impacts or []), impact]
    stop_on_coder_report(repo_dir, state, impact, handback.get("agent_id"), stop_cause)


def route_coder_plan_impact(repo_dir, state, handback, coder_stage):
    impact = stage_plan_impact(repo_dir, state, coder_stage)
    if not impact:
        return False

    stop_cause = coder_impact_stop_cause(impact)
    if stop_cause:
        stop_on_plan_impact_cause(repo_dir, state, handback, impact, stop_cause)
        return True

    state.stage = "impact-coder"
    state.impact = impact
    save_state(repo_dir, state)
    replaced = coder_impact_was_replaced(repo_dir, state)
    emit_plan_impact_modal(impact, repo_dir, replaced=replaced)
    return True


def coder_impact_was_replaced(repo_dir, state):
    # True when a hand-back of a coder at this stage dropped or changed the block that `state.impact` holds.
    stage_reports = [report for report in phase_coder_reports(repo_dir, state)
                     if report["stage"] == state.coder_stage]
    return impact_replaced(stage_reports, state.impact)


def end_unreviewable_report(repo_dir, state, handback, report, outcome, changed_files):
    # Ends the step on a report with nothing to review: the asks coder found every ask already done, a correction put
    # the tree back, or the coder stopped on a blocker. True when it ended the step.
    coder_stage = state.stage
    is_open = left_findings_open(state)
    has_pending_correction = coder_stage == Stage.ASKS_CODER and state.pending_correction is not None
    if outcome == "converged" and not is_open and not has_pending_correction:
        finish_without_review(
            repo_dir, state, changed_files, coder_stage,
            "The asks coder changed nothing, and named where each confirmed ask is already in the code or the passing "
            "check that confirms it. No review "
            "runs. The coder reported:\n" + report)
        return True
    if outcome == "undone" and not is_open and not has_pending_correction:
        finish_without_review(
            repo_dir, state, changed_files, coder_stage,
            "After the correction no ask stays accepted and the tree is back where the asks round began, so no "
            "review runs. The coder reported:\n" + report)
        return True
    if outcome in CODER_STOP_CAUSES:
        # A report that blames the toolkit, or names no cause, stops on that cause even when it changed no file.
        impact = first_plan_impact([report], state.handled_impacts)
        stop_cause = coder_impact_stop_cause(impact) if impact else None
        if stop_cause:
            stop_on_plan_impact_cause(repo_dir, state, handback, impact, stop_cause)
            return True
        stop_on_coder_report(repo_dir, state, report, handback.get("agent_id"), CODER_STOP_CAUSES[outcome])
        return True
    return False


def review_coder_report(repo_dir, state, handback):
    # The hand-back gate stays up through a stop that resumes the same coder, whose next hand-back runs the checks
    # again. Any other outcome ends the coder's gate.
    is_ask_fix = state.stage == Stage.ASKS_CODER
    route_coder_report(repo_dir, state, handback)
    if not is_ask_fix and stop_kind(state) != StopKind.CODER_RESUMABLE:
        run_coder_gate(repo_dir, "clear")


def route_coder_report(repo_dir, state, handback):
    coder_stage = state.stage
    is_ask_fix = coder_stage == Stage.ASKS_CODER
    report = coder_message_without_gate_stamp(handback.get("message", ""))

    if stop_when_head_left_base(repo_dir, state, report, handback):
        return

    gate = None if is_ask_fix else gate_results(repo_dir)
    gate_lines = state.gate_lines
    if not is_ask_fix:
        _code, gate_lines = run_coder_gate(repo_dir, "summary")
    state.flagged = coder_flagged(state, gate, report, is_ask_fix)
    state.flagged += outside_scope_flags(read_events(repo_dir, state.run_id))

    changed_now = file_hashes(repo_dir)
    changed_files = coder_changed_files(repo_dir, state, changed_now)
    outcome = unreviewable_outcome(repo_dir, state, report, changed_files, changed_now)
    if end_unreviewable_report(repo_dir, state, handback, report, outcome, changed_files):
        return

    is_open = left_findings_open(state)
    has_pending_correction = is_ask_fix and state.pending_correction is not None
    asks_baseline = snapshot_part(state, "asks")
    asks_changed_files = None
    if is_ask_fix and asks_baseline is not None:
        asks_changed_files = asks_coder_changed_files(changed_now, asks_baseline)
    if has_pending_correction:
        record_coder_report(repo_dir, state, report, gate, changed_files, asks_changed_files)
        return dispatch_correction_coder(repo_dir, state)

    if asks_changed_files is not None and not is_open:
        # The review after an asks-coder covers only what the asks-coder changed. A state from before the asks snapshot
        # existed keeps the whole-phase scope, and so does a review that left findings open (a cap, or a critical
        # blocker with asks): its carried findings may sit in any file.
        changed_files = asks_changed_files
        if all(name.lower().endswith(DOCS_SUFFIXES) for name in changed_files):
            return finish_without_review(repo_dir, state, changed_files, coder_stage,
                                         "The asks coder changed only docs files. No review runs on them.")

    record_coder_report(repo_dir, state, report, gate, changed_files, asks_changed_files)
    state.gate_lines = gate_lines
    if route_coder_plan_impact(repo_dir, state, handback, coder_stage):
        return

    state.plan_impact = "none"
    save_state(repo_dir, state)
    emit_review_dispatch(repo_dir, state)


def command_after_coder(repo_dir, state, args):
    if not wait_for_handback(repo_dir, state, RESUME_VERB):
        return

    handback = take_handback(repo_dir, state, CODER, NO_CODER_REPORT)
    if handback is None:
        return
    review_coder_report(repo_dir, state, handback)


# ---------- resume ----------

def run_guarded_verb(verb, handler, args):
    repo_dir = repo_root_or_exit()
    os.chdir(repo_dir)
    state = load_state(repo_dir)
    if guarded_verb_runs(verb, state):
        return handler(repo_dir, state, args)

    refusal = VERB_REFUSALS[verb]
    if verb in GO_ON_REFUSAL_VERBS:
        return emit("go-on", refusal)
    return refuse(refusal, script_command(RESUME_VERB))


def stopped_coder_report(repo_dir, state):
    # The last message of the coder the run stopped on, or a note that none was saved.
    for report in reversed(phase_coder_reports(repo_dir, state)):
        if report["agent_id"] == state.stop.agent_id and report["messages"]:
            return report["messages"][-1]

    deny_reason = newest_later_phase_deny_reason(read_events(repo_dir, state.run_id), state.stop.agent_id)
    if deny_reason:
        return f"(no report saved; the hand-back gate denied an earlier attempt) {deny_reason}"
    return "(none saved)"


def coder_answer_sent(repo_dir, state):
    # The user's answer reached the stopped coder: it handed back already, or a SendMessage to it is logged after the
    # stop.
    if awaited_handback(repo_dir, state) is not None:
        return True
    coder_id = state.stop.agent_id
    return sent_message_since(repo_dir, state, state.stop.at, None if coder_id == "unknown" else coder_id)


def review_answer_sent(repo_dir, state):
    # The user resumed the review-loop that the wait cap stopped on, or it handed back late on its own.
    launch_id = awaited_agent_id(repo_dir, state)
    if launch_id is None:
        return False
    return (awaited_handback(repo_dir, state) is not None
            or sent_message_since(repo_dir, state, state.stop.at, launch_id))


def review_goes_on(repo_dir, state):
    # The review-loop the wait cap stopped on goes on: a review script is on record (after-review stops on one that
    # has gone), the user resumed it, or it handed back late on its own.
    return bool(state.review_script_pid) or review_answer_sent(repo_dir, state)


# What the saved run and its log show, for a row of the route table whose step hangs on it.
OBSERVATIONS = {
    "dispatch-recorded": lambda repo_dir, state: dispatch_since(state) is not None,
    "coder-answer-sent": coder_answer_sent,
    "review-goes-on": review_goes_on,
}


def next_resume_step(repo_dir, state):
    # The step that comes next for the saved run, by its row in the route table. Pure: it reads and changes nothing.
    step = resume_step(repo_dir, state, OBSERVATIONS)
    if state is None:
        return step

    # The run's own coder or review-loop is back: taking its hand-back reads the plan again, so the plan edits it made
    # do not make the run stale. Only when that read adopts the phase: otherwise the stale check decides now.
    is_own_handback = (step in ("after-coder", "after-review")
                       and awaited_handback(repo_dir, state) is not None
                       and own_phase_text(repo_dir, state) is not None)
    if not is_own_handback and stale_phase_reason(repo_dir, state):
        return STALE_PHASE_STEP
    return step


def ask_about_stopped_coder(repo_dir, state, answer=None):
    # With the user's answer from `resume <answer>`, the question tells the main session to send that answer on.
    phase_tick = (f" If the user says Phase {state.phase} is done, run `tick {state.phase}`."
                 if state.plan and state.phase else "")
    report = stopped_coder_report(repo_dir, state)
    restart_instruction_text = stopped_run_restart_instruction(repo_dir, state)
    coder_id = state.stop.agent_id
    if answer is None:
        send_step = f"Send the user's answer to agent {coder_id} with SendMessage, then run resume."
    else:
        send_step = (f"The user answered: {answer}. Send that answer to agent {coder_id} with SendMessage, then "
                     "run resume.")

    ask_user(
        repo_dir,
        f"The coder stopped and waits for the user's answer. Its report: {report}. {send_step}{phase_tick} To "
        f"dispatch a new coder for the phase, {restart_instruction_text}.",
    )


def saved_run_line(state):
    stop_reason = stop_kind(state)
    return f"The run is at stage {state.stage}" + (f" with stop reason {stop_reason}." if stop_reason else ".")


def ask_about_saved_state(repo_dir, state):
    # The stop for a saved run that waits on no answer the script can take: it prints the state and how to start over.
    saved_line = saved_run_line(state)
    restart_instruction_text = stopped_run_restart_instruction(repo_dir, state)
    status_command = script_command("status")
    ask_user(repo_dir, f"{saved_line} Run `{status_command}` to read the saved state. To start the phase over, "
             f"{restart_instruction_text}.")


def ask_to_fix_the_cause(repo_dir, state):
    # A stop whose cause the user fixes outside the run; the verb of the run's row goes on once it is fixed.
    saved_line = saved_run_line(state)
    verb = ROUTES[state_key(state)].verb
    ask_user(repo_dir, f"{saved_line} When the cause is fixed, run `{verb}`.")


def resume_closing_skill(repo_dir, state):
    # A closing phase that outlives its session: a resume invokes its skill again, with the phase's plan section.
    section = current_phase_text(repo_dir, state.plan, state.phase)
    skill = plan_format.closing_skill(state.title)
    emit_closing_skill(repo_dir, state.plan, state.phase, state.title, skill, section, state.run_notes)


def ask_about_review_cap(repo_dir, state):
    ask_user(repo_dir, "The review-loop never handed back. If the user resumes it with SendMessage, run "
             f"resume. If it died, {REVIEW_AGAIN_INVOKE}.")


def ask_about_critical_blocker(repo_dir, state):
    status_command = script_command("status")
    opening_sentence = blocker_stop_text()[stop_kind(state)][0]
    ask_user(repo_dir, f"The run stopped: {opening_sentence} Present it to the user. Run "
             f"`{status_command}` to read the saved state. Then, {blocker_stop_next_step(state)}")


def ask_about_stale_phase(repo_dir, state):
    # The plan moved under the saved run: going on would run the old phase. Dropping the run starts the plan's next open
    # phase.
    modifier_words = [state.modifier] if state.modifier else []
    restart_command = script_command(" ".join(["start --restart", state.plan, *modifier_words]))
    ask_user(repo_dir, f"The saved run is stale: {stale_phase_reason(repo_dir, state)}. Ask the user whether to drop "
             f"the stale run and start the plan's next open phase. If so, run `{restart_command}`. The working tree "
             "stays as it is.")


def ask_about_coder_cap(repo_dir, state):
    restart_instruction_text = stopped_run_restart_instruction(repo_dir, state)
    ask_user(repo_dir, "The coder never handed back and cannot be resumed here: it is a plan-edit coder, or "
             f"its launch has no agent id. To dispatch the phase coder again, {restart_instruction_text}.")


def resume_impact_question(repo_dir, state):
    replaced = state.stage == Stage.IMPACT_CODER and coder_impact_was_replaced(repo_dir, state)
    return emit_plan_impact_modal(state.impact, repo_dir, state.carried_findings or [], replaced=replaced)


# The step `resume` takes, by the name the route table gives it.
STEPS = {
    "start": lambda repo_dir, state: command_start([]),
    "done": lambda repo_dir, state: command_start(carried_start_words(state)),
    "after-coder": lambda repo_dir, state: command_after_coder(repo_dir, state, []),
    "after-review": lambda repo_dir, state: command_after_review(repo_dir, state, []),
    "after-plan-edit": lambda repo_dir, state: command_after_plan_edit(repo_dir, state, []),
    "review-again": lambda repo_dir, state: command_review_again(repo_dir, state, []),
    "ask-impact": resume_impact_question,
    "ask-asks": lambda repo_dir, state: ask_the_user(repo_dir, state, state.asks),
    "closing-skill": resume_closing_skill,
    "ask-coder": ask_about_stopped_coder, "ask-review-cap": ask_about_review_cap,
    "ask-coder-cap": ask_about_coder_cap, "ask-stale-phase": ask_about_stale_phase,
    "ask-critical-blocker": ask_about_critical_blocker, "ask-cause-fixed": ask_to_fix_the_cause,
    "ask-status": ask_about_saved_state,
}


def command_resume(args):
    repo_dir = repo_root_or_exit()
    os.chdir(repo_dir)
    state = load_state(repo_dir)
    step = next_resume_step(repo_dir, state)
    # With no run open, the arguments are new work: a task file or task text that came with no verb.
    if args and step in ("start", "done"):
        return command_start(args)
    # A stale phase outranks the route, so an answer sent while a stopped coder waits would otherwise be refused as
    # "no stopped coder waits": say the phase is stale instead.
    if args and step == STALE_PHASE_STEP:
        return ask_about_stale_phase(repo_dir, state)

    # Only a coder that waits for the user's answer takes one: `resume <answer>`.
    if args and step != "ask-coder":
        reason, commands, notes, stop = resume_text_refusal(repo_dir, state, args)
        return refuse(reason, *commands, notes=notes, stop=stop)

    if state is not None and StageFact.RESUME_CLEARS_SAY in STAGE_FACTS[state.stage]:
        clear_say(repo_dir)

    if args:
        return ask_about_stopped_coder(repo_dir, state, answer=" ".join(args))
    STEPS[step](repo_dir, state)


def abort_dropped_lines(repo_dir, state, criteria_message, archive_path, script_pid,
                       review_script_was_running):
    # What `abort` tells the user it dropped, one line each. The dispatch line reads the launch log, so call it before
    # the state moves.
    lines = [f"Dropped the /code run: {phase_label(state)} at stage {state.stage}."]
    if criteria_message:
        lines.append(criteria_message)

    if script_pid is not None and review_script_was_running:
        lines.append(f"Killed the review loop script (pid {script_pid}) and its claude calls.")
    elif script_pid is not None:
        lines.append(f"The review loop script (pid {script_pid}) had already exited.")
    elif state.dispatch_at is not None:
        agent_id = awaited_agent_id(repo_dir, state)
        agent_text = f"agent {agent_id}" if agent_id else "an agent whose launch was not logged"
        lines.append(f"A dispatch was still open: {agent_text} may still be running. The user can stop it.")

    if state.baseline is not None:
        left_files = changed_since_baseline(state, file_hashes(repo_dir))
        if left_files:
            lines.append("The run left these uncommitted files in the working tree. Abort did not touch them: "
                         + ", ".join(left_files))

    lines.append(f"The run's state is archived in {archive_path}.")
    return lines


def command_abort(args):
    repo_dir = repo_root_or_exit()
    os.chdir(repo_dir)
    if args:
        return refuse("abort takes no arguments.", script_command("abort"))

    state = load_state(repo_dir)
    if state is None or state.stage == Stage.DONE:
        return emit("stop", "No /code run is open here. Nothing was dropped.")

    criteria_message = None
    if state.criteria_guard is not None:
        criteria_message = settle_criteria_guard(repo_dir, state, branch_label(repo_dir))
    # The archive holds the run as it stood, with its criteria copy settled.
    archived_text = state_text(state)

    review_script_was_running = review_script_running(state)
    script_pid = stop_review_script(state)
    clear_say(repo_dir)
    clear_question(repo_dir)
    run_coder_gate(repo_dir, "clear")

    directory = state_dir(repo_dir)
    archive_path = directory / f"aborted-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    lines = abort_dropped_lines(repo_dir, state, criteria_message, archive_path, script_pid,
                                review_script_was_running)
    script_utils.write_text_atomically(archive_path, archived_text)
    drop_state(repo_dir)
    emit("stop", *lines)


def command_guide(args):
    # The guidance of the main session for the open run. It never stops the run: every outcome is `go-on`.
    repo_dir = repo_root_or_exit()
    text = " ".join(args).strip()
    if not text:
        return emit("go-on", "The guidance was not recorded: no text was given to guide.")

    state = load_state(repo_dir)
    if state is None or state.stage == Stage.DONE:
        return emit("go-on", "The guidance was not recorded: no /code run is open here.")

    record_guidance(state, text)
    save_state(repo_dir, state)
    emit("go-on", "Guidance recorded. Every later coder and review dispatch of this run carries it.")


def command_status():
    state = load_state(repo_root_or_exit())
    if state is None:
        print("no code-step state")
        return

    print(state_text(state))


VERBS_THAT_TAKE_REPO = ("asks-done", "correct-ruling")


def enter_named_checkout(named_repo):
    # The checkout `--repo` names must hold an open run, of any session: a session started after /clear resumes a run
    # that still names the old session. The stage guard of the verb refuses a wrong stage. False after a stop.
    named_root = script_utils.repo_root(named_repo) if named_repo else None
    if named_root is None:
        emit("stop", f"--repo {named_repo or ''} is not a path inside a git repo. Tell the user.")
        return False

    named_state = load_state(named_root)
    if named_state is None or not is_run_open(named_state):
        emit("stop", f"{named_root} holds no open /code run, so --repo {named_repo} names no run. "
             f"Tell the user. `{script_command('status')}` run from a checkout shows its run.")
        return False

    os.chdir(named_root)
    return True


def enter_run_checkout(verb="", named_repo=None):
    # Every verb after `start` runs in the checkout of the session's open run, wherever the shell stands: a run started
    # in a worktree or another repo keeps every step there. `--repo` (asks-done, correct-ruling) names that checkout.
    # With several open runs and none in the cwd, asks-done goes on with the one run that waits at its asks. False
    # after a stop.
    if named_repo is not None:
        return enter_named_checkout(named_repo)

    session_id = session_pin()
    if session_id is None:
        return True

    cwd_repo = script_utils.repo_root(os.getcwd())
    open_run_repos = resume_run_repos(cwd_repo, session_id)
    if open_run_repos == [cwd_repo]:
        return True

    if len(open_run_repos) > 1 and verb == "asks-done":
        asks_run_repos = [repo for repo in open_run_repos if load_state(repo).stage == Stage.ASKS]
        if len(asks_run_repos) > 1:
            checkout_lines = [f"- {repo}" for repo in asks_run_repos]
            emit("stop", "This session has open asks in each of these checkouts, and the current directory is in "
                 "none of them:", *checkout_lines,
                 "Run asks-done again with `--repo <checkout>` for the run the user answered.")
            return False

        if asks_run_repos:
            open_run_repos = asks_run_repos

    if len(open_run_repos) > 1:
        checkout_lines = [f"- {repo}" for repo in open_run_repos]
        emit("stop", "This session has an open /code run in each of these checkouts, and the current directory is in "
             "none of them:", *checkout_lines,
             "Tell the user. On their word, run the verb again from the checkout of the run to go on with: "
             f"`cd <checkout> && {script_command('status')}` shows that run.")
        return False

    if open_run_repos:
        os.chdir(open_run_repos[0])
    return True


def run_status():
    try:
        if not enter_run_checkout():
            return
        command_status()
    except StateFileError as error:
        print(error)


HOOK_VERBS = {
    "hook": command_hook, "log-hook": command_log_hook, "dispatch-hook": command_dispatch_hook,
    "plan-hook": command_plan_hook, "stop-hook": command_stop_hook, "say-hook": command_say_hook,
    "launch-hook": command_launch_hook,
}
VERB_USAGE = ("usage: code_step.py start|resume|decide|asks-done|correct-ruling|skill-done|verify|review-again|tick"
              "|abort|guide|hook|log-hook|dispatch-hook|launch-hook|stop-hook|say-hook|status|plan|plan-hook")


@contextlib.contextmanager
def verb_lock(repo, verb):
    # One verb at a time on a run: a second copy (a resumed agent beside a live one) stops before it reads the state.
    # abort skips the lock so a stuck verb can still be dropped. A checkout with no state folder has no run to share.
    folder = state_dir(repo)
    if verb == "abort" or folder is None or not folder.is_dir():
        yield True
        return

    with open(folder / "verb.lock", "a+") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock_file.seek(0)
            holder = lock_file.read().strip() or "unknown"
            emit("stop", f"another code_step verb is running on this run (pid {holder}). Do not start another verb "
                 "and do not resume a second copy of the agent: wait for that verb's output.")
            yield False
            return

        lock_file.truncate(0)
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        yield True


def run_verb(verb, handler, args):
    try:
        named_repo = None
        if verb in VERBS_THAT_TAKE_REPO:
            args, named_repo = script_utils.pop_option(args, "--repo")
        if verb != "start" and not enter_run_checkout(verb, named_repo):
            return

        repo = repo_root_or_exit()
        with verb_lock(repo, verb) as holds_lock:
            if not holds_lock:
                return

            if verb not in VERBS_THAT_KEEP_QUESTION:
                clear_question(repo)
            if verb in VERBS_THAT_CLEAR_SAY:
                clear_say(repo)

            # The verb writes the state once, at its end, and only then prints what to do next.
            with verb_transaction():
                if verb in GUARDED_VERBS:
                    run_guarded_verb(verb, handler, args)
                else:
                    handler(args)
    except StateFileError as error:
        emit("stop", f"{error}. Tell the user to delete that file, then run `start`.")


def main():
    verb = sys.argv[1] if len(sys.argv) > 1 else ""
    args = sys.argv[2:]
    # `start` prints its own usage. Every other verb prints its here, before any state is read.
    if print_usage_if_asked(verb, args, is_hook=verb in HOOK_VERBS):
        return
    check_verb_arguments(verb, args)
    verbs = {"start": command_start, RESUME_VERB: command_resume, "decide": command_decide,
             "asks-done": command_asks_done, "correct-ruling": command_correct_ruling,
             "skill-done": command_skill_done_with_question, "verify": command_verify,
             "tick": command_tick, "review-again": command_review_again, "abort": command_abort,
             "guide": command_guide}
    if verb in HOOK_VERBS:
        return HOOK_VERBS[verb]()
    if verb == "plan":
        return command_plan(args)
    if verb == "status":
        return run_status()
    if verb not in verbs:
        sys.exit(VERB_USAGE)
    run_verb(verb, verbs[verb], args)


if __name__ == "__main__":
    main()
