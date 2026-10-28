#!/usr/bin/env python3
"""code_step.py: the routing of /code as a script. The forked Sonnet subagent of /code runs one verb, reads its
ACTION lines, does exactly that, and runs the next verb. The script builds every prompt and every argument.

  code_step.py start [<plan>] [+fast|+deep] [--phase <id>] [--restart] [<run notes>]
                                                next phase of the plan (or the named one): checks, gate, packet, the
                                                exact coder dispatch. `start --help` prints usage. --restart drops an
                                                unfinished run first.
  code_step.py start --task "<text>"           planless work: the coder dispatch without gate or packet
  code_step.py start --task-file <path>        the same, with the text read from a file
  code_step.py start --repo <path> ...         run in that checkout, not the current directory (a `Repo: <path>` first
                                                line in the task file does the same)
  code_step.py resume                           do the next step of the saved run, whatever stage or stop it is in
  code_step.py resume <text>                    the answer to a stopped coder; with no run open, the same as start
  code_step.py decide <adopt|keep> --by <user|session> --ruling "<the decision in one line>"
                                                only --by user is the user's own word: a session ruling never changes
                                                a criterion
  code_step.py decide discuss                   ask the user how to rule when the code and the plan disagree; records
                                                nothing
  code_step.py asks-done [--by <user|session>] <outcome>...
                                                log the answer to each ask[] entry, then run the phase gates;
                                                --by session when the session ruled itself, default user
  code_step.py skill-done <pass|fail> [--evidence "<text>"]... [--finding "<text>"]...
                                                a closing phase's skill returned: mark it done (pass) or stop (fail);
                                                at pass, give one --evidence per open Success Criteria item and the
                                                script writes it into the plan
  code_step.py verify                           re-run the phase gates after a failed Automated Verification was fixed
  code_step.py review-again                     dispatch the review loop again on the same diff, after its packet did
                                                not parse
  code_step.py tick <phase id>                  mark a phase done that the user finished outside /code
  code_step.py abort                            end the open run on purpose: settle its criteria copy, clear its gate
                                                and texts, archive state.json as aborted-<UTC time>.json; the working
                                                tree stays as it is
  code_step.py hook                             PreToolUse hook on SubagentHandback: deny the fork's hand-back while a
                                                dispatched agent is still out
  code_step.py log-hook                         PostToolUse hook on Agent|SubagentHandback|SendMessage: log launch,
                                                hand-back and resume events of the run
  code_step.py dispatch-hook                    PreToolUse hook on Agent: deny a coder or review-loop launch whose
                                                prompt lacks the saved dispatch prompt, or a repeat launch of a coder
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

The code is split in files that import one way: code_step_core (state, event log, hand-back matcher, output),
code_step_boundary (criteria guard, verification runner, phase boundary), code_step_hooks, code_step_gates (gate
commands), code_step_start (the start verb), code_step_report (reading a coder report), code_step_review
(plan-impact modal, plan-edit dispatch, review dispatch, review packet, asks), and this file."""
import json
import os
import pathlib
import sys
import time

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import plan_format
import script_utils
from code_step_boundary import (
    command_tick,
    command_verify,
    finish_phase,
    settle_criteria_guard,
    verification_format_failure,
)
from code_step_closing import command_skill_done_with_question
from code_step_core import (
    CODER,
    CODER_STAGES,
    HOOK_STAGES,
    RESUME_VERB,
    SCRIPTS_DIR,
    StateFileError,
    ask_user,
    awaited_agent_id,
    awaited_handback,
    awaits_resumed_coder,
    awaits_resumed_review,
    branch_label,
    clear_question,
    clear_say,
    committed_since,
    dispatch_since,
    emit,
    file_hashes,
    holds_open_run,
    load_state,
    phase_coder_reports,
    refuse,
    repo_root_or_exit,
    restart_instruction,
    review_script_running,
    save_state,
    say,
    script_command,
    sent_message_since,
    session_open_run_repos,
    session_pin,
    state_dir,
    stop_review_script,
    stop_with_question,
    take_handback,
    timed_command,
    wait_for_handback,
)
from code_step_hooks import (
    command_dispatch_hook,
    command_hook,
    command_log_hook,
    command_plan_hook,
    command_say_hook,
    command_stop_hook,
)
from code_step_report import (
    behavior_lines,
    coder_flags,
    coder_message_without_gate_stamp,
    every_accepted_ask_already_done,
    first_plan_impact,
    gate_results,
    recommends_eng_spec,
    resolve_report_paths,
    tests_run_text,
    why_by_file,
)
from code_step_review import (
    STAGE_GUARDS,
    ask_the_user,
    command_after_plan_edit,
    command_after_review,
    command_asks_done,
    command_decide,
    command_review_again,
    emit_plan_impact_modal,
    emit_review_dispatch,
    is_capped_review,
    prior_issues,
)
from code_step_start import RESUME_ALIASES, command_start, emit_closing_skill, phase_label
from script_utils import run_command

WAITING_STAGES = ("asks", "impact-coder", "impact-review", "skill", "plan-coder")
# These verbs open a new /code run after the user answered. The last run's say.md text was already handed back.
VERBS_THAT_CLEAR_SAY = ("decide", "asks-done", "verify", "review-again")
# The saved stage of a run and the step that comes next for it. `stopped` and an unknown stage are routed by code.
STAGE_ROUTES = {
    "coder": "after-coder", "asks-coder": "after-coder", "review": "after-review", "plan-coder": "after-plan-edit",
    "impact-coder": "ask-impact", "impact-review": "ask-impact", "asks": "ask-asks", "done": "done",
}
NO_CODER_REPORT = ("No coder report was saved. The log-hook (code_step.py log-hook) is not installed or the coder "
                   "never handed back. Tell the user.")


# ---------- plan check ----------

PLAN_USAGE = "usage: code_step.py plan check [--final]|parse <path>"


def command_plan(args):
    # `plan check --final <path>` also fails a spec whose criteria file was never written.
    if "--help" in args or "-h" in args:
        print(PLAN_USAGE)
        sys.exit(0)

    final = args[1:2] == ["--final"] and args[0] == "check"
    path_args = args[2:] if final else args[1:]
    if not path_args or args[0] not in ("check", "parse"):
        sys.exit(PLAN_USAGE)
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
    verification_failure = verification_format_failure(plan_lines, plan_path, pathlib.Path.cwd(), plan["entries"])
    if verification_failure:
        print(verification_failure)
    ac_failures = plan_format.spec_ac_failures(pathlib.Path(plan_path))
    for row in ac_failures:
        print(row)
    criteria_failure = plan_format.missing_criteria_failure(pathlib.Path(plan_path)) if final else None
    if criteria_failure:
        print(criteria_failure)
    sys.exit(1 if plan["failures"] or manual_failure or verification_failure or ac_failures or criteria_failure else 0)


# ---------- coder hand-back ----------

DOCS_SUFFIXES = (".md", ".mdx", ".rst", ".txt")


def asks_coder_changed_files(changed_now, asks_baseline):
    # The files whose hash differs between the snapshot taken at the asks-coder dispatch and now, new and deleted
    # included.
    names = set(changed_now) | set(asks_baseline)
    return sorted(name for name in names if changed_now.get(name) != asks_baseline.get(name))


def finish_without_review(repo_dir, state, changed_files, coder_stage, say_text):
    # No review has anything to cover: run the phase's verification commands and tick, as after a clean review.
    state.update({"files": changed_files, "coderStage": coder_stage, "stage": "review"})
    save_state(repo_dir, state)
    say(repo_dir, say_text)
    return finish_phase(repo_dir, state)


def coder_flagged(state, gate, report, is_ask_fix):
    # The report's open points, with the hand-back gate's cap and the flags an asks-coder inherits.
    flagged = list(state.get("flagged", [])) if is_ask_fix else []
    capped = [coder for coder in (gate or {"coders": {}})["coders"].values() if coder["result"] == "cap"]
    for coder in capped:
        flagged.append("hand-back gate cap: " + ", ".join(coder["failed"]) + " still failing after 3 denials")
    return flagged + coder_flags(report)


def changed_since_baseline(state, changed_now):
    # The files of the working tree that differ from the run's baseline.
    baseline = state["baseline"]
    return [name for name, digest in changed_now.items() if name not in baseline or baseline[name] != digest]


def coder_changed_files(repo_dir, state, changed_now):
    # The files the phase changed since its baseline, and the files the coder committed itself.
    changed_files = changed_since_baseline(state, changed_now)
    committed = committed_since(repo_dir, state.get("baseHead"))
    return changed_files + [name for name in committed if name not in changed_files]


def unreviewable_outcome(repo_dir, state, report, changed_files, changed_now):
    # "converged" when the asks coder changed nothing and named, for each confirmed ask, the file:line that already
    # does it or the check that passed; "stop" for a report with no reviewable change or one whose marker line
    # recommends /eng-spec; else None. Any other report with no change (a failed edit, a blocked hook, a question)
    # stops.
    is_ask_fix = state["stage"] == "asks-coder"
    asks_coder_changed_nothing = is_ask_fix and changed_now == state.get("asksBaseline")
    escalates = recommends_eng_spec(report)
    report_raises_blocker = escalates or bool(first_plan_impact([report])) or bool(coder_flags(report))
    if asks_coder_changed_nothing and not report_raises_blocker and every_accepted_ask_already_done(
            repo_dir, state, report):
        return "converged"
    if not changed_files or asks_coder_changed_nothing or escalates:
        return "stop"
    return None


CODER_REPORT_STOP_LINES = 6


def stop_on_coder_report(repo_dir, state, report, agent_id):
    # The run stops on the coder's report: the user answers it, and the coder resumed with SendMessage goes on.
    state["stage"] = "stopped"
    state.pop("stopReason", None)
    state["resumableCoderAt"] = time.time()
    state["resumableCoderId"] = agent_id or "unknown"
    state.pop("dispatchAt", None)
    save_state(repo_dir, state)
    tick_text = (f" If the user says Phase {state['phase']} is already done, invoke Skill code with `tick "
                f"{state['phase']}`; do that only on the user's word." if state.get("plan") and state.get("phase")
                else "")
    resume_text = (" If the user answers the coder's blocker, resume that coder with SendMessage, then run "
                  f"{timed_command(RESUME_VERB)}.")
    report_lines = [line for line in report.splitlines() if line.strip()][:CODER_REPORT_STOP_LINES]
    next_step = (f"if the user answers the coder's blocker, resume that coder with SendMessage, then run "
                 f"`{script_command(RESUME_VERB)}`. To dispatch a new coder for the phase, "
                 f"{restart_instruction(state)}.")
    stop_with_question(
        repo_dir, "the coder produced no reviewable change, or recommended /eng-spec.", report_lines, next_step,
        "The coder produced no reviewable change, or recommended /eng-spec. Do not dispatch a "
        "review. Do not mark the phase done." + tick_text + resume_text
        + " Relay the coder's report to the user:", report)


def record_coder_report(repo_dir, state, report, gate, changed_files):
    # Saves what the review needs from a reviewable report: behavior, why notes, tests run and files.
    coder_stage = state["stage"]
    is_ask_fix = coder_stage == "asks-coder"
    behavior = behavior_lines(report)
    why_groups = resolve_report_paths(why_by_file(report), changed_files)
    tests_run = tests_run_text(gate, state)
    if is_ask_fix:
        # The ask-fix coder's behavior stays off the phase's own behavior (its Implemented line and Behavior delta).
        state["askFixBehavior"] = list(state.get("askFixBehavior", [])) + behavior
        behavior = list(state.get("behavior", []))
        for path, notes in state["why"].items():
            if path in changed_files:
                why_groups[path] = notes + why_groups.get(path, [])
        tests_run = state["testsRun"] + "; ask-fix coder -> ran its own checks"
        state.update({"iter": 0, "spec_iter": 0, "priorIssues": prior_issues(state["acceptedAsks"])})
    state.update({"behavior": behavior, "exception": bool(state["flagged"]), "files": changed_files,
                  "why": why_groups, "testsRun": tests_run, "coderStage": coder_stage})


def stage_plan_impact(repo_dir, state, coder_stage):
    # The first PLAN-IMPACT block in any hand-back, or attempt to hand back, of the coders this run dispatched at this
    # stage. A hand-back that a gate denied still counts: the coder may send only the fix on its retry.
    messages = [coder_message_without_gate_stamp(message)
                for report in phase_coder_reports(repo_dir, state) if report["stage"] == coder_stage
                for message in report["attempts"] + report["messages"]]
    return first_plan_impact(messages)


def review_coder_report(repo_dir, state, handback):
    coder_stage = state["stage"]
    is_ask_fix = coder_stage == "asks-coder"
    report = coder_message_without_gate_stamp(handback.get("message", ""))
    gate = None if is_ask_fix else gate_results(repo_dir)
    gate_lines = state.get("gateLines", "")
    if not is_ask_fix:
        _code, gate_lines = run_command(["python3", str(SCRIPTS_DIR / "code" / "coder_gate.py"), "clear"], repo_dir)
    state["flagged"] = coder_flagged(state, gate, report, is_ask_fix)

    changed_now = file_hashes(repo_dir)
    changed_files = coder_changed_files(repo_dir, state, changed_now)
    outcome = unreviewable_outcome(repo_dir, state, report, changed_files, changed_now)
    is_capped = is_capped_review(state)
    if outcome == "converged" and not is_capped:
        return finish_without_review(
            repo_dir, state, changed_files, coder_stage,
            "The asks coder changed nothing, and named where each confirmed ask is already in the code or the passing "
            "check that confirms it. No review "
            "runs. The coder reported:\n" + report)
    if outcome == "stop":
        return stop_on_coder_report(repo_dir, state, report, handback.get("agent_id"))

    asks_baseline = state.get("asksBaseline")
    if is_ask_fix and asks_baseline is not None and not is_capped:
        # The review after an asks-coder covers only what the asks-coder changed. A state from before asksBaseline
        # existed keeps the whole-phase scope, and so does a capped review: its carried findings may sit in any file.
        changed_files = asks_coder_changed_files(changed_now, asks_baseline)
        if all(name.lower().endswith(DOCS_SUFFIXES) for name in changed_files):
            return finish_without_review(repo_dir, state, changed_files, coder_stage,
                                         "The asks coder changed only docs files. No review runs on them.")

    record_coder_report(repo_dir, state, report, gate, changed_files)
    state["gateLines"] = gate_lines
    impact = stage_plan_impact(repo_dir, state, coder_stage)
    if impact:
        state.update({"stage": "impact-coder", "impact": impact})
        save_state(repo_dir, state)
        return emit_plan_impact_modal(impact, repo_dir)

    state["planImpact"] = "none"
    save_state(repo_dir, state)
    emit_review_dispatch(repo_dir, state)


def command_after_coder(repo_dir, state, args):
    if state["stage"] not in CODER_STAGES and not awaits_resumed_coder(state):
        return refuse("no coder dispatch is pending any more.", script_command(RESUME_VERB))
    if not wait_for_handback(repo_dir, state, RESUME_VERB):
        return

    handback = take_handback(repo_dir, state, CODER, NO_CODER_REPORT)
    if handback is None:
        return
    review_coder_report(repo_dir, state, handback)


# ---------- resume ----------

def run_guarded_verb(verb, handler, args):
    guard = STAGE_GUARDS[verb]
    repo_dir = repo_root_or_exit()
    os.chdir(repo_dir)
    state = load_state(repo_dir)
    at_stage = state is not None and state["stage"] in guard["stages"]
    reason_allowed = "stopReasons" not in guard or (state or {}).get("stopReason") in guard["stopReasons"]
    resumed_review = verb == "review-again" and state is not None and awaits_resumed_review(state)
    if not (at_stage and reason_allowed) and not resumed_review:
        return refuse(guard["message"], script_command(RESUME_VERB))
    handler(repo_dir, state, args)


def stopped_coder_report(repo_dir, state):
    # The last message of the coder the run stopped on, or a note that none was saved.
    for report in reversed(phase_coder_reports(repo_dir, state)):
        if report["agent_id"] == state.get("resumableCoderId") and report["messages"]:
            return report["messages"][-1]
    return "(none saved)"


def coder_answer_sent(repo_dir, state):
    # The user's answer reached the stopped coder: it handed back already, or a SendMessage to it is logged after the
    # stop.
    if awaited_handback(repo_dir, state) is not None:
        return True
    coder_id = state.get("resumableCoderId")
    return sent_message_since(repo_dir, state, state["resumableCoderAt"], None if coder_id == "unknown" else coder_id)


def review_answer_sent(repo_dir, state):
    # The user resumed the review-loop that the wait cap stopped on, or it handed back late on its own.
    launch_id = awaited_agent_id(repo_dir, state)
    if launch_id is None:
        return False
    return (awaited_handback(repo_dir, state) is not None
            or sent_message_since(repo_dir, state, state["resumableReview"], launch_id))


def stopped_route(repo_dir, state):
    if awaits_resumed_coder(state):
        return "after-coder" if coder_answer_sent(repo_dir, state) else "ask-coder"
    if awaits_resumed_review(state):
        if state.get("reviewScriptPid"):
            return "after-review"
        return "after-review" if review_answer_sent(repo_dir, state) else "ask-review-cap"

    return "ask-coder-cap" if state.get("stopReason") == "coder-cap" else "ask-unknown"


def resume_route(repo_dir, state):
    # The step that comes next for the saved run, by its stage and stop reason. Pure: it reads and changes nothing.
    if state is None:
        return "start"

    stage = state["stage"]
    if stage in HOOK_STAGES and dispatch_since(state) is None:
        return "ask-unknown"
    if stage == "stopped":
        return stopped_route(repo_dir, state)
    return STAGE_ROUTES.get(stage, "ask-unknown")


def ask_about_stopped_coder(repo_dir, state, answer=None):
    # With the user's answer from `resume <answer>`, the question tells the main session to send that answer on.
    phase_tick = (f" If the user says Phase {state['phase']} is done, run `tick {state['phase']}`."
                 if state.get("plan") and state.get("phase") else "")
    report = stopped_coder_report(repo_dir, state)
    restart_instruction_text = restart_instruction(state)
    coder_id = state["resumableCoderId"]
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


def ask_about_unrecorded_state(repo_dir, state):
    # The fallback stop for a saved state that no route covers: it prints the state and the command that goes on.
    stage = state["stage"]
    if stage == "skill":
        return resume_closing_skill(repo_dir, state)

    stop_reason = state.get("stopReason")
    saved = f"The run is at stage {stage}" + (f" with stop reason {stop_reason}." if stop_reason else ".")
    guarded_verb = next((verb for verb, guard in STAGE_GUARDS.items()
                        if stage in guard["stages"] and stop_reason in guard.get("stopReasons", ())), None)
    if guarded_verb:
        next_step = f"When the cause is fixed, run `{guarded_verb}`."
    else:
        restart_instruction_text = restart_instruction(state)
        status_command = script_command("status")
        next_step = (
            f"Run `{status_command}` to read the saved state. To start the phase over, {restart_instruction_text}."
        )
    ask_user(repo_dir, f"{saved} {next_step}")


def resume_closing_skill(repo_dir, state):
    # A closing phase that outlives its session: a resume invokes its skill again, with the phase's plan section.
    plan_lines = (repo_dir / state["plan"]).read_text().split("\n")
    section = plan_format.phase_text(plan_lines, state["phase"])
    skill = plan_format.closing_skill(state["title"])
    emit_closing_skill(repo_dir, state["plan"], state["phase"], state["title"], skill, section)


def resume_start(repo_dir, state):
    command_start([])


def resume_done(repo_dir, state):
    command_start([state["modifier"]] if state.get("modifier") else [])


def resume_after_coder(repo_dir, state):
    command_after_coder(repo_dir, state, [])


def resume_after_review(repo_dir, state):
    command_after_review(repo_dir, state, [])


def resume_after_plan_edit(repo_dir, state):
    command_after_plan_edit(repo_dir, state, [])


def ask_about_impact(repo_dir, state):
    emit_plan_impact_modal(state["impact"], repo_dir, state.get("carriedFindings", []))


def ask_about_asks(repo_dir, state):
    ask_the_user(repo_dir, state, state["asks"])


def ask_about_review_cap(repo_dir, state):
    ask_user(repo_dir, "The review-loop never handed back. If the user resumes it with SendMessage, run "
             "resume. If it died, invoke Skill code with `review-again`.")


def ask_about_coder_cap(repo_dir, state):
    restart_instruction_text = restart_instruction(state)
    ask_user(repo_dir, "The coder never handed back and cannot be resumed here: it is a plan-edit coder, or "
             f"its launch has no agent id. To dispatch the phase coder again, {restart_instruction_text}.")


# The step a route name runs. A route no entry names prints the saved state.
RESUME_HANDLERS = {
    "start": resume_start, "done": resume_done, "after-coder": resume_after_coder,
    "after-review": resume_after_review, "after-plan-edit": resume_after_plan_edit, "ask-impact": ask_about_impact,
    "ask-asks": ask_about_asks, "ask-coder": ask_about_stopped_coder, "ask-review-cap": ask_about_review_cap,
    "ask-coder-cap": ask_about_coder_cap,
}


def command_resume(args):
    repo_dir = repo_root_or_exit()
    os.chdir(repo_dir)
    state = load_state(repo_dir)
    route = resume_route(repo_dir, state)
    # With no run open, the arguments are new work: a task file or task text that came with no verb.
    if args and route in ("start", "done"):
        return command_start(args)

    # Only a coder that waits for the user's answer takes one: `resume <answer>`.
    if args and route != "ask-coder":
        return refuse("resume takes no arguments here: no stopped coder waits for an answer.",
                      script_command(RESUME_VERB), notes=("For new work, use `start --task \"<text>\"`.",))

    if state is not None and (state["stage"] == "stopped" or state["stage"] in WAITING_STAGES):
        clear_say(repo_dir)

    if args:
        return ask_about_stopped_coder(repo_dir, state, answer=" ".join(args))
    RESUME_HANDLERS.get(route, ask_about_unrecorded_state)(repo_dir, state)


def abort_dropped_lines(repo_dir, state, criteria_message, archive_path, script_pid,
                       review_script_was_running):
    # What `abort` tells the user it dropped, one line each. The dispatch line reads the launch log, so call it before
    # the state moves.
    lines = [f"Dropped the /code run: {phase_label(state)} at stage {state['stage']}."]
    if criteria_message:
        lines.append(criteria_message)

    if script_pid is not None and review_script_was_running:
        lines.append(f"Killed the review loop script (pid {script_pid}) and its claude calls.")
    elif script_pid is not None:
        lines.append(f"The review loop script (pid {script_pid}) had already exited.")
    elif state.get("dispatchAt") is not None:
        agent_id = awaited_agent_id(repo_dir, state)
        agent_text = f"agent {agent_id}" if agent_id else "an agent whose launch was not logged"
        lines.append(f"A dispatch was still open: {agent_text} may still be running. The user can stop it.")

    if state.get("baseline") is not None:
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
    if state is None or state.get("stage") in (None, "done"):
        return emit("stop", "No /code run is open here. Nothing was dropped.")

    criteria_message = None
    if state.get("criteriaGuard") is not None:
        criteria_message = settle_criteria_guard(repo_dir, state, branch_label(repo_dir))
        save_state(repo_dir, state)

    review_script_was_running = review_script_running(state)
    script_pid = stop_review_script(state)
    clear_say(repo_dir)
    clear_question(repo_dir)
    run_command(["python3", str(SCRIPTS_DIR / "code" / "coder_gate.py"), "clear"], repo_dir)

    directory = state_dir(repo_dir)
    archive_path = directory / f"aborted-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    lines = abort_dropped_lines(repo_dir, state, criteria_message, archive_path, script_pid,
                                review_script_was_running)
    (directory / "state.json").rename(archive_path)
    emit("stop", *lines)


def command_status():
    state = load_state(repo_root_or_exit())
    print(json.dumps(state, indent=1) if state else "no code-step state")


def enter_run_checkout():
    # Every verb after `start` runs in the checkout of the session's open run, wherever the shell stands: a run started
    # in a worktree or another repo keeps every step there. False after a stop.
    session_id = session_pin()
    cwd_repo = script_utils.repo_root(os.getcwd())
    if session_id is None or (cwd_repo is not None and holds_open_run(cwd_repo, session_id)):
        return True

    open_run_repos = session_open_run_repos(session_id)
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
}
VERB_USAGE = ("usage: code_step.py start|resume|decide|asks-done|skill-done|verify|review-again|tick|abort|hook"
              "|log-hook|dispatch-hook|stop-hook|say-hook|status|plan|plan-hook")


def run_verb(verb, handler, args):
    try:
        if verb != "start" and not enter_run_checkout():
            return

        clear_question(repo_root_or_exit())
        if verb in VERBS_THAT_CLEAR_SAY:
            clear_say(repo_root_or_exit())

        if verb in STAGE_GUARDS:
            run_guarded_verb(verb, handler, args)
        else:
            handler(args)
    except StateFileError as error:
        emit("stop", f"{error}. Tell the user to delete that file, then run `start`.")


def main():
    verb = sys.argv[1] if len(sys.argv) > 1 else ""
    args = sys.argv[2:]
    verbs = {"start": command_start, RESUME_VERB: command_resume, "decide": command_decide,
             "asks-done": command_asks_done, "skill-done": command_skill_done_with_question, "verify": command_verify,
             "tick": command_tick, "review-again": command_review_again, "abort": command_abort}
    verbs.update(dict.fromkeys(RESUME_ALIASES, command_resume))
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
