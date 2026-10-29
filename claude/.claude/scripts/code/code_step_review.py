"""The review half of code_step: plan-impact modal, plan-edit dispatch, review dispatch, review packet and asks."""
import os
import re
import shutil
import subprocess
import sys
import time

import plan_format
import review_asks
import script_utils
from code_step_asks import (
    ASKS_DONE_USAGE,
    asks_coder_prompt,
    numbered_ask_lines,
    preset_ask_outcome,
    split_asks_done_args,
)
from code_step_boundary import (
    criteria_file,
    finish_phase,
    mark_review_gate_clean,
    save_criteria_guard,
    settle_criteria_guard,
)
from code_step_core import (
    CLAUDE_DIR,
    PLAN_EDIT_STOP_REASONS,
    RESUME_VERB,
    REVIEW_LOOP,
    REVIEW_LOOP_SCRIPT,
    REVIEW_SCRIPT_AGENT_PREFIX,
    ask_user,
    awaited_agent_id,
    awaited_handback,
    awaits_resumed_review,
    branch_label,
    dispatch_marker,
    emit,
    emit_dispatch,
    file_hashes,
    load_handback,
    load_state,
    log_event,
    open_dispatch,
    phase_code_in_place,
    phase_coder_reports,
    plan_edit_open_choices,
    prompt_with_gate_env,
    record_dispatch,
    record_ruled_asks,
    restart_instruction,
    ruled_asks_lines,
    run_session_id,
    runs_review_script,
    save_state,
    say,
    script_command,
    session_pin,
    state_dir,
    stop_review_script,
    stop_with_question,
    take_handback,
    timed_command,
    wait_for_handback,
    wait_for_loop_stop,
)
from code_step_report import change_line, coder_message_without_gate_stamp
from code_step_usage import DECIDE_COMMAND
from script_utils import ask_text, git_output, run_command
from source_paths import is_counted_source

PLAN_IMPACT_OPTIONS = ["Adopt plan change", "Keep plan as written", "Discuss"]
DECISION_WORDS = {"adopt": PLAN_IMPACT_OPTIONS[0], "keep": PLAN_IMPACT_OPTIONS[1], "discuss": PLAN_IMPACT_OPTIONS[2]}
# The state each guarded verb needs: the stages it may run at, the stop reasons it accepts when the stage is "stopped",
# and the refusal text when the state is anything else. `start`, `tick` and `resume` run at any stage and are not in
# the table. A review-loop resumed after the wait cap also counts for review-again, and a converged review of the
# phase's code counts for verify.
STAGE_GUARDS = {
    "decide": {"stages": ("impact-coder", "impact-review"),
               "message": "decide needs a pending PLAN-IMPACT and one word: adopt, keep or discuss."},
    "review-again": {"stages": ("stopped",),
                     "stopReasons": ("invalid-packet", "cap-reached", "false-clean", "tool-fault", "critical-blocker",
                                     "setup-fault", "check-unverified"),
                     "message": "review-again ran with no unreadable review packet, capped review, crashed review "
                                "call, unmarked review gate, critical blocker, setup fault, a full check that showed "
                                "no test run or silent review-loop pending."},
    "asks-done": {"stages": ("asks",), "message": ASKS_DONE_USAGE},
    "skill-done": {"stages": ("skill",), "message": "skill-done ran with no closing-phase skill pending."},
    "verify": {"stages": ("stopped",), "stopReasons": PLAN_EDIT_STOP_REASONS,
               "message": "verify ran with no converged review, failed Automated Verification or unparsed Manual "
                          "Verification pending."},
}


def guarded_verb_runs(verb, state):
    # The saved state lets a STAGE_GUARDS verb run.
    if state is None:
        return False

    guard = STAGE_GUARDS[verb]
    at_stage = state["stage"] in guard["stages"]
    reason_allowed = "stopReasons" not in guard or state.get("stopReason") in guard["stopReasons"]
    if at_stage and reason_allowed:
        return True
    if verb == "review-again":
        return awaits_resumed_review(state)
    if verb == "verify":
        return phase_code_in_place(state)
    return False


NO_REVIEW_PACKET = ("No review-loop packet was saved. The log-hook (code_step.py log-hook) is not installed. "
                    "Tell the user.")


def preset_decision(repo_dir):
    # A pre-answered decision for runs with no AskUserQuestion (claude -p, bench): env var or a file in the state dir.
    word = os.environ.get("CODE_STEP_IMPACT_DECISION", "").strip().lower()
    preset_file = state_dir(repo_dir) / "impact-decision"
    if not word and preset_file.exists():
        word = preset_file.read_text().strip().lower()
    return word if word in ("adopt", "keep") else None


def decide_call(word):
    return f"`decide {word} --by user --ruling \"<the decision in one line>\"`"


DECIDE_BY_NOTE = ("If the user told you to make the call yourself, or you rule without asking, pass `--by session` in "
                  "place of `--by user`. A session ruling never changes the acceptance criteria.")


def carried_question_lines(carried):
    # The findings the plan-impact round left open, shown under the question so the user sees them with the ruling.
    if not carried:
        return []
    return ["Also open from the same review round. The review after the ruling gets these too:",
            *[f"- {line}" for line in carried], ""]


def emit_plan_impact_modal(impact, repo_dir, carried=()):
    word = preset_decision(repo_dir)
    if word:
        print(f"PLAN-IMPACT answered by the pre-set decision '{word}'. No question to the user.")
        state = load_state(repo_dir)
        return command_decide(repo_dir, state, [word, "--by", "session", "--ruling",
                                                f"pre-set decision '{word}'; no user was asked"],
                              ruling_by="the pre-set decision")
    if not plan_format.changes_acceptance_criteria(impact):
        print("PLAN-IMPACT changes no acceptance criterion, so the plan follows the code. No question to the user.")
        state = load_state(repo_dir)
        return command_decide(repo_dir, state, ["adopt", "--by", "session", "--ruling",
                                                plan_format.below_criteria_ruling(impact)])
    ask_user(repo_dir, "the code and the plan disagree. Ask the user this question in plain text and wait for the "
             "answer. Then invoke Skill code with the args after the option the user chose, with the ruling in one "
             "line, in your own words, as the --ruling text. Do not quote the user.",
             impact, "",
             *carried_question_lines(carried),
             f"1. {PLAN_IMPACT_OPTIONS[0]} (a coder rewrites the plan steps to match the ruling): "
             f"{decide_call('adopt')}",
             f"2. {PLAN_IMPACT_OPTIONS[1]}: {decide_call('keep')}",
             f"3. {PLAN_IMPACT_OPTIONS[2]}: talk it through here, then invoke Skill code with "
             f"{decide_call('adopt')} or {decide_call('keep')}",
             DECIDE_BY_NOTE)


def record_deviation(repo_dir, state):
    ruling = state["ruling"]
    entry = plan_format.ruling_deviation(state["phase"], ruling["decision"], ruling["by"], ruling["at"],
                                         ruling["words"], state["impact"])
    plan_format.append_deviation(repo_dir / state["plan"], entry)


def split_decide_args(args):
    # The decision word, who ruled (`--by user|session`, None when missing), then the words after `--ruling`,
    # joined when the caller left them unquoted.
    word = args[0].lower() if args else ""
    ruling_at = args.index("--ruling") if "--ruling" in args else len(args)
    by_words = args[:ruling_at]
    by = by_words[by_words.index("--by") + 1] if "--by" in by_words[:-1] else None
    ruling_words = " ".join(args[ruling_at + 1:])
    return word, by, ruling_words.strip()


def resolved_plan_impact(state):
    # review-loop reads a block that starts RESOLVED as settled, so it reviews against the ruling instead of
    # returning the question again.
    ruling = state["ruling"]
    if ruling["byUser"]:
        resolved = "the user ruled on this disagreement"
    elif ruling["by"] == "the pre-set decision":
        resolved = "the pre-set decision ruled on this disagreement, not the user"
    else:
        resolved = "the session ruled on this disagreement, not the user"
    lines = [f"RESOLVED: {resolved}. Review the code against the ruling. It is not an open question.",
             f"Decision: {ruling['decision']}",
             f"Ruled by: {ruling['by']}, at {ruling['at']}",
             "The ruling:"]
    lines += ["  " + line for line in ruling["words"].splitlines()]
    lines.append("The disagreement it settles:")
    lines += ["  " + line for line in state["impact"].splitlines()]
    return "\n".join(lines)


def decision_for_word(repo_dir, state, word):
    # The decision the word names, or None after the stop or the question it printed (a blank word, an unknown word, or
    # discuss).
    if not word:
        return emit("stop", STAGE_GUARDS["decide"]["message"])
    decision = DECISION_WORDS.get(word)
    if decision is None:
        return emit("stop", "decide takes adopt, keep or discuss.")
    if decision == "Discuss":
        return ask_user(repo_dir, "discuss this disagreement between the code and the plan with the user in plain "
                        f"words. When the user chooses, invoke Skill code with {decide_call('adopt')} or "
                        f"{decide_call('keep')}. {DECIDE_BY_NOTE}", state["impact"])
    return decision


def ruling_problem(word, by, ruling_words):
    # The stop text for a ruling that lacks who made it or what it says, or None.
    if by not in ("user", "session"):
        return f"decide {word} needs --by user or --by session. Usage: `{DECIDE_COMMAND}`. {DECIDE_BY_NOTE}"
    if not ruling_words:
        return (f"decide {word} needs the ruling's words: {decide_call(word)}. {DECIDE_BY_NOTE} "
                "Hand back and ask the main session for them.")
    return None


def record_ruling(repo_dir, state, decision, by, ruling_words, ruling_by):
    by_user = by == "user" and not ruling_by
    ruling_name = ruling_by or plan_format.ruling_owner(repo_dir, by)
    state["ruling"] = {"decision": decision, "words": ruling_words, "by": ruling_name, "byUser": by_user,
                       "at": time.strftime("%Y-%m-%d %H:%M")}
    if not by_user and state.get("plan") and criteria_file(repo_dir, state):
        print("The acceptance criteria stay as written: verify-branch reports any criterion the code now fails as "
              "failing.")
    if state.get("plan"):
        record_deviation(repo_dir, state)
    state["planImpact"] = resolved_plan_impact(state)
    # A ruling opens a new review: the round cap of the review that raised the question does not carry over.
    state["iter"] = 0


def command_decide(repo_dir, state, args, ruling_by=None):
    word, by, ruling_words = split_decide_args(args)
    decision = decision_for_word(repo_dir, state, word)
    if decision is None:
        return

    problem = ruling_problem(word, by, ruling_words)
    if problem:
        return emit("stop", problem)
    if state.get("plan") and not (repo_dir / state["plan"]).is_file():
        return emit("stop", f"The plan file {state['plan']} is missing (a branch switch?). Tell the user.")

    record_ruling(repo_dir, state, decision, by, ruling_words, ruling_by)
    if decision == PLAN_IMPACT_OPTIONS[0]:
        return emit_plan_edit_dispatch(repo_dir, state)
    emit_review_dispatch(repo_dir, state)


def planless_plan_edit_prompt(state):
    # A planless run has no plan file of its own: the coder finds the branch's plan docs the ruling overturns.
    ruling = state["ruling"]
    ruled_by = "The user ruled" if ruling["byUser"] else "The ruling"
    return "\n".join([
        "No plan file is tied to this run. The review found that the code and this branch's plan docs disagree:",
        "",
        state["impact"],
        "",
        f"{ruled_by} ({ruling['by']}, {ruling['at']}):",
        "",
        ruling["words"],
        "",
        "Find the plan docs of this branch that state the side the ruling overturns: start with the files the "
        "disagreement names, then `docs/plans/`. In each one, rewrite every step, Automated Verification command and "
        "Success Criteria line that the ruling contradicts, so that it states the ruling, and add an entry under its "
        "`## Plan Deviations` section (add the section when it has none) with the ruling, who made it and when. Edit "
        "Markdown plan docs only: no code, no test and no acceptance criteria file, and run no check. When no plan "
        "doc states the overturned side, change nothing and say so.",
        "",
        "Report each line you changed as `<file>:<line number>: <new text>`. Ask the user nothing and make no choice "
        "that is theirs. For each choice the ruling leaves open, a change to an acceptance criterion included, end "
        "the report with one line: `OPEN CHOICE: <the choice in one line>`. The script hands each such line to the "
        "user.",
    ])


def plan_edit_prompt(state, criteria_path):
    ruling = state["ruling"]
    user_ruled = ruling["byUser"]
    edit_scope = f"the plan file {state['plan']}"
    if criteria_path and user_ruled:
        edit_scope += f" and its acceptance criteria file {criteria_path}"
    lines = [
        f"Edit only {edit_scope}. In Phase {state['phase']}, the code and the plan disagreed:",
        "",
        state["impact"],
        "",
        (f"The user ruled ({ruling['by']}, {ruling['at']}):" if user_ruled
         else f"The ruling ({ruling['by']}, {ruling['at']}):"),
        "",
        ruling["words"],
        "",
        "Rewrite each step, Automated Verification command and Success Criteria line of the plan that the ruling "
        "contradicts, so that the plan states the ruling. Keep every other line as it is. Leave the "
        "`## Plan Deviations` section as it is. Edit no code and no test, and run no check.",
    ]
    if criteria_path and not user_ruled:
        lines += ["", f"Do not edit {criteria_path}. Only the user's own sign-off changes an acceptance criterion."]
    if criteria_path and user_ruled:
        lines += [
            "",
            f"Rewrite each criterion in {criteria_path} that the ruling changes, so that it states the ruling. Under "
            f"each one you rewrite, add `Signed off by {ruling['by']}, {ruling['at']}: <the change in one line>`. "
            "Keep every other criterion as it is.",
        ]
    lines += [
        "",
        "Report each line you changed as `<file>:<line number>: <new text>`. Ask the user nothing and make no choice "
        "that is theirs. For each choice the ruling leaves open, end the report with one line: "
        "`OPEN CHOICE: <the choice in one line>`. The script hands each such line to the user.",
    ]
    return "\n".join(lines)


def emit_plan_edit_dispatch(repo_dir, state):
    # An adopted change stays only in Plan Deviations unless the steps that contradict it change too, and the
    # reviewer then reads the old step and raises the same disagreement again.
    ruling = state["ruling"]
    has_plan = bool(state.get("plan"))
    criteria_path = criteria_file(repo_dir, state) if has_plan else None
    if has_plan and not ruling["byUser"]:
        save_criteria_guard(repo_dir, state)
    state.update({"stage": "plan-coder", "planEditBaseline": file_hashes(repo_dir),
                  "followUpBefore": change_snapshot(repo_dir)})
    open_dispatch(state)
    save_state(repo_dir, state)

    if not has_plan:
        headline = (f"The plan change was adopted by {ruling['by']}. Dispatch a coder to rewrite the branch's plan "
                    "docs it contradicts.")
        prompt = planless_plan_edit_prompt(state)
        return emit_dispatch(repo_dir, state, RESUME_VERB, headline, prompt=prompt, agent="coder")

    prompt = plan_edit_prompt(state, criteria_path)
    if ruling["byUser"]:
        criteria_clause = " and acceptance criteria" if criteria_path else ""
        headline = (f"The user adopted the plan change. Dispatch a coder to rewrite the plan steps{criteria_clause} "
                    "it contradicts.")
    else:
        unchanged_clause = " The acceptance criteria do not change." if criteria_path else ""
        headline = (f"The plan change was adopted by {ruling['by']}. Dispatch a coder to rewrite the plan steps it "
                    f"contradicts.{unchanged_clause}")
    emit_dispatch(repo_dir, state, RESUME_VERB, headline, prompt=prompt, agent="coder")


def command_review_again(repo_dir, state, args):
    stop_review_script(state)
    is_capped_stop = state.get("stopReason") == "cap-reached"
    if is_capped_stop:
        state["iter"] = 0
    state.pop("stopReason", None)
    state.pop("resumableReview", None)
    state.pop("resumeWaitAt", None)
    # A failed review that ran the structure pass runs it again; one that skipped it skips it again. A capped review
    # ran it on this diff already.
    if not is_capped_stop and not state.get("structurePassSkipped"):
        state.pop("reviewRan", None)
    emit_review_dispatch(repo_dir, state)


def flag_stray_plan_edits(state, stray_files):
    # A file the plan-edit coder had no leave to change goes to the review, flagged.
    if not stray_files:
        return

    state["files"] += [name for name in stray_files if name not in state["files"]]
    state["flagged"].append("the plan-edit coder also changed " + ", ".join(stray_files))
    state["exception"] = True


def settle_plan_edit(repo_dir, state, edited_files):
    # Flag the stray edits, refresh the phase text from the edited plan, and return the note for the user.
    criteria_path = criteria_file(repo_dir, state)
    allowed_files = (state["plan"], criteria_path) if state["ruling"]["byUser"] else (state["plan"],)
    flag_stray_plan_edits(state, [name for name in edited_files if name not in allowed_files])

    plan_lines = (repo_dir / state["plan"]).read_text().splitlines()
    state["phaseText"] = plan_format.phase_text(plan_lines, state["phase"])

    plan_note = f"The plan {state['plan']} now states the ruling."
    if criteria_path and criteria_path in edited_files and state["ruling"]["byUser"]:
        plan_note += f" The acceptance criteria in {criteria_path} changed too: read them before you stage."
    return plan_note


def is_planless_plan_doc(name):
    # A Markdown doc the planless plan-edit coder may change: any but an acceptance criteria file.
    return name.endswith(".md") and os.path.basename(name) != "acceptance-criteria.md"


def settle_planless_plan_edit(state, edited_files):
    # The edited plan docs join the review's files, any other edit is flagged; returns the note for the user.
    plan_docs = [name for name in edited_files if is_planless_plan_doc(name)]
    flag_stray_plan_edits(state, [name for name in edited_files if name not in plan_docs])
    state["files"] += [name for name in plan_docs if name not in state["files"]]

    if not plan_docs:
        return "The plan-edit coder changed no plan doc."
    return f"The plan docs {', '.join(plan_docs)} now state the ruling."


def command_after_plan_edit(repo_dir, state, args):
    if not wait_for_handback(repo_dir, state, RESUME_VERB):
        return
    state["sessionId"] = session_pin() or state.get("sessionId")
    plan_edit_handback = awaited_handback(repo_dir, state) or {}
    open_choices = plan_edit_open_choices(plan_edit_handback.get("message", ""))

    had_criteria_guard = state.get("criteriaGuard") is not None
    criteria_message = settle_criteria_guard(repo_dir, state, branch_label(repo_dir))
    if criteria_message:
        say(repo_dir, criteria_message)

    if had_criteria_guard:
        save_state(repo_dir, state)

    baseline = state.pop("planEditBaseline")
    changed_now = file_hashes(repo_dir)
    edited_files = [name for name, digest in changed_now.items() if baseline.get(name) != digest]

    if state.get("plan"):
        plan_note = settle_plan_edit(repo_dir, state, edited_files)
    else:
        plan_note = settle_planless_plan_edit(state, edited_files)
    say(repo_dir, plan_note)
    if open_choices:
        choice_lines = [f"- {choice}" for choice in open_choices]
        say(repo_dir, "\n".join(["The plan-edit coder left these choices to the user:", *choice_lines]))

    emit_review_dispatch(repo_dir, state)


def handoff_block(repo_dir, state):
    lines = ["handoff:", "  files:"]
    behavior_fallback = state["behavior"][0] if state.get("behavior") else None
    for path in state["files"]:
        lines.append(f"    - path: {path}")
        lines.append(f"      change: {state['changes'].get(path) or behavior_fallback or 'changed by the coder'}")
        notes = state["why"].get(path)
        if notes:
            lines.append("      why:")
            for note in notes:
                lines.append(f"        - lines: {note['lines']}")
                lines.append(f"          note: {note['note']}")
    if state.get("priorIssues"):
        lines.append("  prior-issues:")
        for prior_issue in state["priorIssues"]:
            lines.append(f"    - issue: {prior_issue['issue']}")
            lines.append("      status: fixed")
            lines.append(f"      file: {prior_issue['file'] or '-'}")
    ruled_asks = ruled_asks_lines(repo_dir, state.get("plan"))
    if ruled_asks:
        lines.append("  ruled-asks:")
        lines += [f"    - {ruled_ask}" for ruled_ask in ruled_asks]
    lines.append(f"  tests-run: {state['testsRun']}")
    lines.append("  flagged: " + ("; ".join(state["flagged"]) if state["flagged"] else "none"))
    plan_impact = state.get("planImpact", "none")
    if plan_impact == "none":
        lines.append("  plan_impact: none")
    else:
        lines.append("  plan_impact: |")
        lines += ["    " + line for line in plan_impact.splitlines()]
    if state.get("carriedFindings"):
        lines.append("  carried-findings:  # left open by the last review round; review them too")
        lines += [f"    - {carried}" for carried in state["carriedFindings"]]
    lines.append(f"  iter: {state.get('iter', 0)}")
    if state.get("spec_iter"):
        lines.append(f"  spec_iter: {state['spec_iter']}")
    return "\n".join(lines)


SMALL_FOLLOW_UP_LINES = 40


def change_snapshot(repo_dir):
    # Added lines per file (tracked diff against HEAD, and the line count of each untracked file) and the files that
    # are new, so the change a coder makes is the difference between two snapshots.
    added = {}
    new_files = set()
    for row in (git_output(repo_dir, "diff", "--numstat", "HEAD") or "").split("\n"):
        columns = row.split("\t")
        if len(columns) == 3:
            added[columns[2]] = int(columns[0]) if columns[0].isdigit() else 0
    for row in (git_output(repo_dir, "diff", "--name-status", "HEAD") or "").split("\n"):
        columns = row.split("\t")
        if len(columns) == 2 and columns[0] == "A":
            new_files.add(columns[1])
    untracked = (git_output(repo_dir, "ls-files", "--others", "--exclude-standard") or "").split("\n")
    for name in untracked:
        if not name:
            continue
        new_files.add(name)
        path = repo_dir / name
        added[name] = path.read_bytes().count(b"\n") if path.is_file() else 0
    return {"added": added, "newFiles": sorted(new_files)}


def follow_up_is_small(before, after):
    # True when the coder that ran between the two snapshots added under SMALL_FOLLOW_UP_LINES lines to counted
    # non-test files and created no new non-test source file.
    added_lines = sum(max(count - before["added"].get(name, 0), 0) for name, count in after["added"].items()
                     if is_counted_source(name))
    created_source = [name for name in after["newFiles"] if name not in before["newFiles"]
                     and name not in before["added"] and is_counted_source(name)]
    return added_lines < SMALL_FOLLOW_UP_LINES and not created_source


def handoff_report(repo_dir, state):
    # The coders' last hand-back of this run: the phase coders', and the asks coders' after an asks round, joined.
    stages = ["coder"] + (["asks-coder"] if state.get("coderStage") == "asks-coder" else [])
    last_messages = [coder_message_without_gate_stamp(report["messages"][-1])
                     for report in phase_coder_reports(repo_dir, state)
                     if report["stage"] in stages and report["messages"]]
    return "\n\n".join(last_messages)


def emit_review_dispatch(repo_dir, state):
    report = handoff_report(repo_dir, state)
    untracked_text = git_output(repo_dir, "ls-files", "--others", "--exclude-standard") or ""
    untracked_files = set(untracked_text.split("\n"))
    # One behavior sentence describes one file. Across several files it tells the reviewer the wrong change.
    is_one_file = len(state["files"]) == 1
    behavior_fallback = state["behavior"][0] if state["behavior"] and is_one_file else None
    state["changes"] = {path: change_line(report, path, state["files"], behavior_fallback, path in untracked_files)
                        for path in state["files"]}
    header = ["mode: review-first", "caller: code", f"lane: {state['lane']}",
              f"repo: {repo_dir}"]
    if state.get("plan"):
        header.append(f"plan: {state['plan']}")
        if state.get("phase"):
            header.append(f"phase: {state['phase']}")
    if state.get("modifier"):
        header.append(state["modifier"])
    # The structure pass runs on the first review of a phase. A re-review after a ruling, or after a follow-up coder
    # whose own change is small, skips it. The review-loop round count (iter) is a separate matter.
    follow_up_before = state.pop("followUpBefore", None)
    is_small_follow_up = follow_up_before is None or follow_up_is_small(follow_up_before, change_snapshot(repo_dir))
    state["structurePassSkipped"] = bool(state.get("reviewRan") and is_small_follow_up)
    if state["structurePassSkipped"]:
        header.append("structure-pass: skip")
    state["reviewRan"] = True
    prompt = "\n".join(header) + "\n\n" + handoff_block(repo_dir, state)
    state["stage"] = "review"
    state.pop("carriedFindings", None)
    open_dispatch(state)
    state["lastReviewPrompt"] = prompt
    state.pop("reviewStatus", None)
    save_state(repo_dir, state)

    summary = ["Implemented: " + ("; ".join(state["behavior"]) or "see the diff.")]
    if state.get("askFixBehavior"):
        summary.append("Ask-fix: " + "; ".join(state["askFixBehavior"]))
    summary.append("Flagged: " + ("; ".join(state["flagged"]) if state["flagged"] else "none."))
    for path, notes in state["why"].items():
        summary += [f"  {path}:{note['lines']} - {note['note']}" for note in notes]
    summary.append("Auto-dispatching review to check the implementation before committing.")
    say(repo_dir, "\n".join(summary), replaces_blocks_starting="Implemented: ")
    if runs_review_script():
        return launch_review_script(repo_dir, state, prompt)
    emit_dispatch(repo_dir, state, RESUME_VERB, prompt=prompt, agent="review-loop", model="sonnet")


def launch_review_script(repo_dir, state, prompt):
    # The review loop runs as review_loop_script.py, detached. The dispatch and launch rows stand in for the Agent
    # call's, and the store gets the dispatch row the Agent hook writes for a review-loop, so the clean mark finds it.
    module, import_error = load_handback()
    if module is None:
        return emit("stop", f"Cannot launch the review loop script: {import_error}. Tell the user.")

    prompt = prompt_with_gate_env(repo_dir, state, prompt)
    marked_prompt, _dispatch_prompt_file = record_dispatch(repo_dir, state, RESUME_VERB, REVIEW_LOOP, "script", prompt)
    _run_id, dispatch_id = dispatch_marker(marked_prompt)
    agent_id = f"{REVIEW_SCRIPT_AGENT_PREFIX}{state['runId']}-{dispatch_id}"
    session_id = run_session_id(state)
    module.record(session_id, "dispatch", no_review=False, repo=module.reviewed_repo("", repo_dir))

    code_step_dir = state_dir(repo_dir)
    script_dir = code_step_dir / "loop-script" / agent_id
    script_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = script_dir / "prompt.txt"
    prompt_file.write_text(prompt + "\n")
    log_path = script_dir / "script.log"
    command = [sys.executable, str(REVIEW_LOOP_SCRIPT), repo_dir, "--state-dir", str(code_step_dir),
               "--session", session_id, "--run-id", state["runId"], "--agent-id", agent_id,
               "--prompt-file", str(prompt_file)]
    with log_path.open("w") as log:
        process = subprocess.Popen(command, cwd=repo_dir, stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)

    log_event(repo_dir, state["runId"], "launch", session_id, agent_id=agent_id, dispatch=dispatch_id)
    state["reviewScriptPid"] = process.pid
    state["reviewScriptLog"] = str(log_path)
    save_state(repo_dir, state)
    emit("wait", f"The review loop runs as a script; its log is {log_path}. Do not dispatch an agent. Run "
         f"{timed_command(RESUME_VERB)} to wait for its hand-back.")


def load_review_packet(repo_dir, state, message):
    # (hand-back module, packet) of the review-loop's message, or None after the stop it printed.
    module, import_error = load_handback()
    if module is None:
        return emit("stop", f"Cannot read the review-loop packet: {import_error}. Tell the user.")
    try:
        return module, module.load(message)
    except module.PacketError as error:
        state.update({"stage": "stopped", "stopReason": "invalid-packet"})
        save_state(repo_dir, state)
        return emit("stop", "The review-loop packet does not parse. Show the user the raw packet. Problems: "
                    + "; ".join(error.problems), message,
                    "To review the same diff again, invoke Skill code with `review-again`.")


def is_capped_review(state):
    return state.get("reviewStatus") == "cap-reached"


def left_findings_open(state):
    # The review ended with findings open (a cap, or a critical blocker with asks): its rulings go to one more review
    # of the whole phase, and the review gate stays dirty until that review ends clean.
    return state.get("reviewStatus") in ("cap-reached", "critical-blocker")


def review_stop_next_step(state):
    # The command after a review stop: the phase started over, once the user has ruled on the findings.
    return f"after the user rules on the findings, {restart_instruction(state)} to start the phase over."


# The statuses that stop on the packet's blockers: (the question, the instruction to the caller).
BLOCKER_STOP_TEXT = {
    "critical-blocker": ("the review found a critical blocker.",
                         "Review found a critical blocker. Present these to the user. Do not mark the phase done."),
    "setup-fault": ("the review's full check could not run here.",
                    "The full check could not run here. This is a toolkit or environment fault, not a code failure. "
                    "Present these to the user. Do not mark the phase done."),
}


def blocker_stop_next_step(state):
    # A critical blocker the user can clear without a code change (a missing tool, a broken environment) goes on with
    # one command: the review runs again on the same diff.
    review_again_command = script_command("review-again")
    return (f"if the blocker is a fault of the environment and the user has fixed it, run `{review_again_command}` to "
            f"review the same diff again. Otherwise {review_stop_next_step(state)}")


def ask_lines(packet):
    # The reviewer's questions for the user, one line each, with the file and line they concern.
    return [f"{script_utils.one_line(ask_text(item), 800)} ({item.get('file_line', '-')})"
            for item in packet.get("ask", [])]


def stop_on_review_status(repo_dir, state, module, packet):
    # True after the stop or question a packet status that ends the run prints.
    # Imported here: review/ joins sys.path when code_step_core loads, which sorted top-level imports would precede.
    import full_check
    status = packet["status"]
    if status == "plan-impact":
        state.update({"stage": "impact-review", "impact": packet["plan_impact"]})
        save_state(repo_dir, state)
        state["carriedFindings"] = module.carried_findings(packet)
        save_state(repo_dir, state)
        emit_plan_impact_modal(state["impact"], repo_dir, state["carriedFindings"])
        return True
    if packet["tool_fault"]:
        state.update({"stage": "stopped", "stopReason": "tool-fault"})
        save_state(repo_dir, state)
        stop_with_question(
            repo_dir, "a review call failed, so the review did not finish; it found nothing.",
            [packet["tool_fault"]], "to run the review again on the same diff, invoke Skill code with `review-again`.",
            "The review did not run to the end: a tool fault, not a finding. Do not mark the phase done.",
            "Tool fault: " + packet["tool_fault"],
            "To run the review again on the same diff, invoke Skill code with `review-again`.")
        return True
    if status == "critical-blocker" and packet["ask"] and not state.get("blockerCarried"):
        # With asks, the asks route takes the rulings first, as after a cap: the blockers go to the review after it.
        # Only the first blocker stop of a phase takes it, so a preset ruling cannot loop with no human.
        state["blockerCarried"] = True
        state["carriedFindings"] = module.carried_findings(packet, include_asks=False)
        return False
    if status in BLOCKER_STOP_TEXT:
        question, instruction = BLOCKER_STOP_TEXT[status]
        state.update({"stage": "stopped", "stopReason": status})
        save_state(repo_dir, state)

        blocker_lines = ["- " + script_utils.one_line(module.item_text(item, "finding", "file_line"), 800)
                         for item in packet["blockers"]]
        stop_with_question(
            repo_dir, question, [line[2:] for line in blocker_lines], blocker_stop_next_step(state), instruction,
            *blocker_lines, questions=ask_lines(packet))
        return True
    if status in ("converged", "deferred") and full_check.is_unverified(packet["full_check"]):
        # A check that exited 0 printed no test-runner summary, so the check did not show that any test ran: the phase
        # is not verified, so it does not finish.
        state.update({"stage": "stopped", "stopReason": "check-unverified"})
        save_state(repo_dir, state)
        check_command = packet["full_check_command"] or "(not named)"
        configured = full_check.configured_check_command(repo_dir)
        if configured:
            # The repo already names its check, so a Quality check line would change nothing: the runner's output
            # is what the toolkit does not recognize.
            why = ("the full check exited 0 and printed no test-runner summary this toolkit recognizes, so the check "
                   "did not show that any test ran.")
            fix = (f"make the configured check (`{configured}`) print its test runner's summary, or add the "
                   "runner's summary format to SUMMARY_LINES in ~/.claude/scripts/lib/test_run_output.py")
        else:
            why = ("the full check exited 0 and printed no test-runner summary, so the check did not show that any "
                   "test ran.")
            fix = "add a Quality check: `<the command that runs the tests>` line to the repo's CLAUDE.md"
        why_sentence = why[0].upper() + why[1:]
        fix_sentence = fix[0].upper() + fix[1:]
        stop_with_question(
            repo_dir, why, [check_command],
            f"{fix}, then run `{script_command('review-again')}` to review the same diff again.",
            f"{why_sentence} The check ran: `{check_command}`. {fix_sentence}, then run "
            "review-again. Do not mark the phase done.",
            questions=ask_lines(packet))
        return True
    if status == "cap-reached":
        # The first cap of a phase sends the open findings to one more review-loop pass with a fresh round budget.
        # With asks, the asks route takes the rulings first. A cap after that pass stops for a restart.
        # The packet's iter stays on the state: the ask rows of this round log it. The next review dispatch resets it.
        is_second_cap = state.get("capCarried", False)
        state["capCarried"] = True
        if packet["ask"] and not is_second_cap:
            state["carriedFindings"] = module.carried_findings(packet, include_asks=False)
            return False

        state["stage"] = "stopped"
        next_step = review_stop_next_step(state)
        if not is_second_cap:
            state.update({"carriedFindings": module.carried_findings(packet), "stopReason": "cap-reached"})
            next_step = (f"for one more review-loop pass on the same diff, invoke Skill code with `review-again`. "
                         f"Or, {next_step}")
        save_state(repo_dir, state)
        remaining_lines = ["- " + module.item_text(item, "finding", "file_line")
                           for item in packet["findings_remaining"]]
        stop_with_question(
            repo_dir, "the review cap was reached with findings still open.", [line[2:] for line in remaining_lines],
            next_step,
            "The review cap was reached. Report these findings to the user. Do not mark the phase "
            "done. The session stays dirty, so git commit stays blocked.", *remaining_lines,
            questions=ask_lines(packet))
        return True
    return False


def command_after_review(repo_dir, state, args):
    if not wait_for_handback(repo_dir, state, RESUME_VERB):
        return

    # Only the review-loop that the pending review dispatch launched is read. Another review-loop's hand-back is
    # ignored.
    if not awaits_resumed_review(state) and awaited_agent_id(repo_dir, state) is None:
        return emit("stop", "The pending review-loop dispatch has no launch record, so no hand-back can be matched to "
                    f"it. Launch it as printed, then run `{script_command(RESUME_VERB)}` again.")

    handback = take_handback(repo_dir, state, REVIEW_LOOP, NO_REVIEW_PACKET)
    if handback is None:
        return

    loaded = load_review_packet(repo_dir, state, handback.get("message", ""))
    if loaded is None:
        return
    module, packet = loaded

    state["iter"] = packet["iter"]
    if packet["spec_iter"] is not None:
        state["spec_iter"] = packet["spec_iter"]
    state["packet"] = packet
    rewrote_edited = set(state.get("checkRewroteEdited") or []) | set(packet["check_rewrote_edited"])
    created = set(state.get("checkCreated") or []) | set(packet["check_created"])
    changed = set(state.get("checkChanged") or []) | set(packet["check_changed"])
    coder_edited = rewrote_edited | set(packet["files_touched"])
    state["checkCreated"] = sorted(created - coder_edited)
    state["checkChanged"] = sorted(changed - coder_edited)
    state["checkRewroteEdited"] = sorted(rewrote_edited)
    state["reviewStatus"] = packet["status"]
    if stop_on_review_status(repo_dir, state, module, packet):
        return

    save_state(repo_dir, state)

    sections = []
    session_id = run_session_id(state)
    if session_id and module.ended_on_unreviewed_fix(session_id, handback.get("agent_id")):
        sections.append(module.unreviewed_fix_section(packet))
    say(repo_dir, module.render(packet, "code", sections))
    print("The review packet was saved for the user. Do not repeat it.")
    asks = packet["ask"]
    if asks:
        fill_review_ask_ids(repo_dir, state, module, handback, asks)
        return present_asks(repo_dir, state, asks)
    finish_phase(repo_dir, state)


def present_asks(repo_dir, state, asks):
    nvim_jump = os.environ.get("CODE_STEP_NVIM_JUMP", "nvim-jump")
    is_nvim_jump_installed = shutil.which(nvim_jump) is not None

    anchors = []
    for item in asks:
        file_line = item.get("file_line", "")
        question = item.get("question", "")
        is_single_anchor = re.match(r"^[^\s,;]+:\d+(-\d+)?$", file_line) is not None
        if is_single_anchor and is_nvim_jump_installed:
            anchors += ["--note", question[:120], file_line]
    if anchors:
        run_command([nvim_jump, *anchors], repo_dir)
    state["asks"] = asks
    preset_outcome = preset_ask_outcome(repo_dir)
    is_new_ask_after_asks_coder = preset_outcome and preset_outcome != "rejected" and state.get("asksApplied")
    if is_new_ask_after_asks_coder:
        print(f"{len(asks)} new review ask(s) came back after the asks coder ran. The pre-set outcome "
              f"'{preset_outcome}' does not cover them: they go to the user.")
        return ask_the_user(repo_dir, state, asks)
    if preset_outcome:
        print(f"{len(asks)} review ask(s) answered by the pre-set outcome '{preset_outcome}'. No question to the user:")
        say(repo_dir, "\n".join(["Review asks, answered by the pre-set outcome:", *numbered_ask_lines(asks)]))
        log_ask_outcomes(repo_dir, state, [preset_outcome] * len(asks), "session")
        record_ruled_asks(repo_dir, state, [preset_outcome] * len(asks), [None] * len(asks))
        return apply_asks_or_finish(repo_dir, state, [preset_outcome] * len(asks), [None] * len(asks))
    ask_the_user(repo_dir, state, asks)


def ask_the_user(repo_dir, state, asks):
    # A review that left findings open leaves the gate dirty: the review after the rulings marks it.
    is_open = left_findings_open(state)
    if not is_open and not mark_review_gate_clean(repo_dir, state):
        state["stage"] = "stopped"
        save_state(repo_dir, state)
        return

    state["stage"] = "asks"
    save_state(repo_dir, state)
    open_findings_lines = []
    if is_open:
        cause = "The review cap was reached" if is_capped_review(state) else "The review stopped on a critical blocker"
        open_findings_lines = ["", f"{cause} with these still open. After asks-done, "
                                   "one more review-loop pass gets the rulings and these:",
                               *[f"- {line}" for line in state["carriedFindings"]]]
    ask_user(
        repo_dir,
        f"ask the user about each review ask below in plain text and wait for the answers. Each answer is accepted "
        f"(make the proposed change), rejected (leave the code as it stands) or modified (make the user's change "
        f"instead). Then invoke Skill code with the args `asks-done` and {len(asks)} outcome word(s), in order. Put "
        "`--change \"<the user's change text>\"` right after each `modified` word, one per modified ask, as in "
        "`asks-done accepted modified --change \"<text>\" modified --change \"<text>\"` (the example only shows the "
        "shape of the arguments, not how many words). If the repo's CLAUDE.md "
        "hands ask decisions to the session, decide each ask yourself instead of asking, and add `--by session` to "
        "asks-done.",
        *numbered_ask_lines(asks),
        *open_findings_lines,
    )


def ask_logger():
    # Read at call time: CLAUDE_DIR is the toolkit folder this run was pointed at.
    return CLAUDE_DIR / "skills/review/log-review-finding"


def ask_log_context(repo_dir, state):
    # The run fields that an ask row and its outcome row share.
    return {"branch": git_output(repo_dir, "branch", "--show-current") or "-", "lane": state["lane"],
            "scope": "phase", "phase": state.get("phase"), "iter": state["iter"]}


def fill_review_ask_ids(repo_dir, state, module, handback, asks):
    # Give each ask the id of its ask row: the row the loop logged, or one logged here. The ids kept in state belong
    # to one hand-back: reading the same hand-back again logs no row twice, and a later hand-back that asks at the same
    # place starts with none.
    wait_for_loop_stop(state, module, handback)
    handback_key = f"{handback.get('agent_id')}|{handback.get('ts')}"
    if state.get("askIdsHandback") != handback_key:
        state["askIdsHandback"] = handback_key
        state["askIds"] = {}

    kept_ids = state["askIds"]
    keys = [f"{item.get('file_line')}|{item.get('question')}" for item in asks]
    for item, key in zip(asks, keys, strict=True):
        if key in kept_ids and not module.ask_finding_id(item):
            item["finding_id"] = kept_ids[key]

    session_id = run_session_id(state)
    context = ask_log_context(repo_dir, state)
    review_asks.supply_finding_ask_ids(asks, session_id, ask_logger(), context, repo_dir)
    for item, key in zip(asks, keys, strict=True):
        if module.ask_finding_id(item):
            kept_ids[key] = module.ask_finding_id(item)
    save_state(repo_dir, state)


def log_ask_outcomes(repo_dir, state, outcomes, decided_by="user"):
    module, import_error = load_handback()
    if module is None:
        print(f"code-step: ask outcomes not logged: {import_error}", file=sys.stderr)
        return

    context = ask_log_context(repo_dir, state)
    for item, outcome in zip(state["asks"], outcomes, strict=False):
        outcome_row = review_asks.log_ask_outcome(ask_logger(), context, item, outcome, decided_by, repo_dir)
        if outcome_row is None:
            continue
        if outcome_row.code != 0:
            print(f"code-step: ask outcome for finding_id {outcome_row.finding_id} not logged: log-review-finding "
                  f"exited {outcome_row.code}: {script_utils.one_line(outcome_row.output)}", file=sys.stderr)
        elif outcome_row.new_finding_id_note:
            print(f"code-step: {outcome_row.new_finding_id_note}", file=sys.stderr)


def apply_asks_or_finish(repo_dir, state, outcomes, change_texts, also_text=""):
    # An accepted or modified ask is owed work: a coder applies it, then a review of that coder's diff runs (none when
    # the diff is docs only) before the phase can finish. After a review that left findings open (a cap or a critical
    # blocker), that review covers the whole phase and runs even on a docs-only diff, or when every ask was rejected
    # with no coder before it.
    accepted_asks = [
        [item, outcome, change_text]
        for item, outcome, change_text in zip(state["asks"], outcomes, change_texts, strict=False)
        if outcome != "rejected"
    ]
    # Extra text the user gave alongside the outcomes is owed work too: it keeps a coder dispatched when every ask
    # was rejected.
    if not accepted_asks and not also_text and left_findings_open(state):
        state["iter"] = 0
        return emit_review_dispatch(repo_dir, state)
    if not accepted_asks and not also_text:
        state["stage"] = "review"
        save_state(repo_dir, state)
        return finish_phase(repo_dir, state)

    state.update({"stage": "asks-coder", "acceptedAsks": accepted_asks, "asksApplied": True, "asksAlso": also_text,
                  "asksBaseline": file_hashes(repo_dir), "followUpBefore": change_snapshot(repo_dir)})
    open_dispatch(state)
    save_state(repo_dir, state)
    model = "haiku" if state.get("modifier") == "+fast" else None
    if left_findings_open(state):
        review_sentence = ("One more review of the whole phase runs after it, with the findings the last review "
                           "left open.")
    else:
        review_sentence = ("A review of that coder's diff runs after it (none when the diff is docs only) before the "
                           "phase can finish.")
    emit_dispatch(repo_dir, state, RESUME_VERB, "The user accepted review asks. Dispatch a coder to apply them. "
                  + review_sentence, prompt=asks_coder_prompt(accepted_asks, also_text), agent="coder", model=model)


def command_asks_done(repo_dir, state, args):
    outcome_args, decided_by = script_utils.pop_option(args, "--by")
    if decided_by is None:
        decided_by = "user"
    outcomes, given_changes, also_text = split_asks_done_args(outcome_args)
    if decided_by not in ("user", "session") or len(outcomes) != len(state["asks"]) \
            or any(outcome not in review_asks.ASK_OUTCOMES for outcome in outcomes) or given_changes is None \
            or len(given_changes) != outcomes.count("modified"):
        ask_count = len(state["asks"])
        return emit("stop", f"{ASKS_DONE_USAGE} {ask_count} ask(s) wait: give {ask_count} outcome(s), in order.")

    remaining_changes = iter(given_changes)
    change_texts = [next(remaining_changes) if outcome == "modified" else None for outcome in outcomes]
    log_ask_outcomes(repo_dir, state, outcomes, decided_by)
    record_ruled_asks(repo_dir, state, outcomes, change_texts)
    apply_asks_or_finish(repo_dir, state, outcomes, change_texts, also_text)
