"""code_step_boundary.py: the part of code_step.py that guards the plan's acceptance criteria and ends a phase: the
saved criteria copy, the phase boundary and the closing verbs tick and verify.

Imports run one way: code_step_core, code_step_verification, code_step_boundary, code_step_closing, code_step_hooks,
code_step_gates, code_step_start, code_step_report, code_step_review, code_step. The phase-end block text is in
code_step_phase_end; the Automated Verification reader is in code_step_verification, and skill-done in
code_step_closing."""
import contextlib
import datetime
import os
import pathlib
import re
import shlex
import sys
import time

import plan_format
import script_utils
import worktree_snapshot
from check_output import failing_test_quote
from code_step_core import (
    INSTALLED_COMMAND,
    MISSING_PLAN_STOP,
    RESUME_LINE,
    RESUME_VERB,
    REVIEW_SAME_DIFF_AGAIN_LINE,
    branch_label,
    clear_stop,
    current_phase_text,
    emit,
    file_hashes,
    is_dispatch_open,
    load_aborted_plan_state,
    load_handback,
    load_state,
    repo_root_or_exit,
    run_file_path,
    run_session_id,
    save_state,
    say,
    session_pin,
    set_stop,
)
from code_step_phase_end import block_a, block_b_or_c, manual_groups_of
from code_step_usage import VERB_USAGES
from code_step_verification import (
    VERIFICATION_ITEM_SHAPE,
    deferred_verification_items,
    run_verification_commands,
    verification_item_problem,
)

VERIFICATION_OUTPUT_NAME = "verification-output.txt"
TICKET_IN_NAME = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Z0-9]+-\d+)(?![A-Za-z0-9])")


# ---------- acceptance criteria guard ----------

def criteria_rel(plan_rel):
    # The plan's acceptance criteria live beside it.
    return str(pathlib.PurePath(plan_rel).parent / "acceptance-criteria.md")


def criteria_file(repo_dir, state):
    # None when the plan has no criteria file.
    criteria_path = criteria_rel(state["plan"])
    if not (repo_dir / criteria_path).is_file():
        return None
    return criteria_path


def save_criteria_guard(repo_dir, state):
    # Before a plan edit that the user did not rule: remember the criteria file's path and text, or None for "no
    # file", so that restore_criteria can put it back.
    relative_criteria_path = criteria_rel(state["plan"])
    criteria_path = repo_dir / relative_criteria_path
    criteria_text = criteria_path.read_text() if criteria_path.is_file() else None
    state["criteriaGuard"] = {"path": relative_criteria_path, "text": criteria_text}


def save_replaced_criteria(repo_dir, criteria_name, text):
    # Keep the text a restore replaces in the git dir, outside the worktree, one new file per restore.
    folder = script_utils.git_path(repo_dir, "code-step-replaced-criteria")
    folder.mkdir(parents=True, exist_ok=True)

    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    counter = 1
    while True:
        target = folder / f"{stamp}-{counter:02d}-{criteria_name}"
        try:
            with open(target, "x") as handle:
                handle.write(text)
            return target
        except FileExistsError:
            counter += 1


def settle_criteria_guard(repo_dir, state, branch):
    # Resolve the saved criteria copy of a plan edit that the user did not rule. Returns the message for the user,
    # or None when there was nothing to do. The caller saves the state: the guard is popped here.
    if state.get("criteriaGuard") is None:
        return None
    if state.get("branch") != branch:
        state.pop("criteriaGuard")
        return ("The saved acceptance criteria belong to a plan edit on another branch, so the script dropped them "
                "and restored nothing.")
    return restore_criteria(repo_dir, state)


def restore_criteria(repo_dir, state):
    # Put the folder back as it was at the save. The text of a file that differs, or that did not exist at the save,
    # goes to a copy under the git dir first. Returns the message for the user, or None when nothing changed.
    guard = state.pop("criteriaGuard")
    criteria_path = repo_dir / guard["path"]
    if not criteria_path.parent.is_dir():
        return (f"The saved acceptance criteria belong to {guard['path']}, whose folder is gone, so the script "
                "dropped them and restored nothing.")

    if guard["text"] is None:
        return delete_new_criteria(repo_dir, guard, criteria_path)

    changed_note = ""
    if criteria_path.is_file():
        current_text = criteria_path.read_text()
        if current_text == guard["text"]:
            return None
        kept = save_replaced_criteria(repo_dir, criteria_path.name, current_text)
        changed_note = f" The text it replaced is in {kept}."

    criteria_path.write_text(guard["text"])
    return (f"The acceptance criteria in {guard['path']} changed after a ruling the user did not make, and the "
            f"script restored them.{changed_note}")


def delete_new_criteria(repo_dir, guard, criteria_path):
    # The criteria file did not exist at the save: one that appeared since is removed, and its text is kept.
    if not criteria_path.is_file():
        return None
    kept = save_replaced_criteria(repo_dir, criteria_path.name, criteria_path.read_text())
    criteria_path.unlink()
    return (f"No acceptance criteria file existed before a ruling the user did not make, and {guard['path']} "
            f"appeared after it, so the script deleted it. The text it deleted is in {kept}.")


def stop_while_plan_edit_coder_is_out(repo_dir, state, verb_text):
    # A restore or a drop of the saved criteria while the plan-edit coder is still out would leave its later write
    # unchecked. Returns True after printing the stop, with no state changed.
    if state.get("stage") != "plan-coder" or not is_dispatch_open(repo_dir, state):
        return False
    emit("stop", "The plan-edit coder has not reported yet, so the saved acceptance criteria stay as they are. Run "
         f"`! {INSTALLED_COMMAND} {RESUME_VERB}` from the repo root first: it waits for the "
         f"report and restores the criteria. Then run `{verb_text}` again. Tell the user.")
    return True


# ---------- phase boundary ----------

def boundary_decision(state, entries, number):
    # A run started with --headless has no person to sign off a phase: it commits and goes on wherever block B waits.
    block, risk_label = sign_off_decision(state, entries, number)
    if block == "B" and state.get("headless"):
        return "A", f"{risk_label}, headless"
    return block, risk_label


def sign_off_decision(state, entries, number):
    # A run started with --phase N ends after phase N, whatever other phases are still open. A run never starts a phase
    # past an open gated one, so when a gated phase comes first (or only gated phases are open) this is the last phase
    # the run can do.
    open_others = [e for e in plan_format.ordered_pending(entries) if e["number"] != number]
    gated_ahead, next_ungated = plan_format.gate_blockers(open_others)
    is_last = state.get("onlyPhase") == number or bool(gated_ahead) or next_ungated is None
    if is_last:
        return "C", "last phase"
    if number == "1":
        return "B", "low - Phase 1 calibration" if state["risk"] == "low" else state["risk"]
    if state.get("exception"):
        return "B", "low - exception" if state["risk"] == "low" else state["risk"]
    if state["risk"] == "low":
        return "A", "low"
    return "B", "high"


def mark_review_gate_clean(repo_dir, state):
    # The review loop ended clean, so the committing session gets credit for the reviewed tree.
    # Returns False after emitting a stop when the hand-back record shows the loop did not end clean, or when the
    # shared hand-back reader is not installed. Nothing is credited then. The hand-back is read for the session the
    # run is pinned to, which launched the review loop; the reviewed tree is credited to the session that commits.
    module, import_error = load_handback()
    if module is None:
        emit("stop", f"Cannot confirm the review loop ended clean: {import_error}. The review gate is not marked "
             "clean. Tell the user.")
        return False
    # The packet this run read is the record of how its loop ended. The shared hand-back store is keyed by session
    # and can hold an earlier converged hand-back, so it never overrules a packet that did not converge.
    review_status = state.get("reviewStatus")
    if review_status is not None and review_status not in module.CLEAN_STATUSES:
        set_stop(state, "review-not-converged")
        save_state(repo_dir, state)
        emit("stop", f"The phase stays open: its review loop ended {review_status}, not converged. Nothing is "
             "committed and the review gate is not marked clean. Report to the user what the review waits on.")
        return False
    reviewing_session = run_session_id(state)
    committing_session = session_pin() or state.get("sessionId") or "unknown"
    # The tree the loop reviewed: a later coder dispatch that edits nothing leaves it unchanged, so its commit passes.
    reason, reviewed_repo = module.record_clean_review(reviewing_session, committing_session)
    if reason:
        set_stop(state, "false-clean")
        save_state(repo_dir, state)
        emit("stop", f"The review gate is not marked clean: {reason}. Nothing is committed.",
             REVIEW_SAME_DIFF_AGAIN_LINE)
        return False
    if not reviewed_repo:
        print("[review-commit-gate] The stored review dispatch names no repo, so no tree was recorded as "
              "reviewed.", file=sys.stderr)
    return True


def diff_stat_rows(repo_dir, files):
    # One "path | +added -deleted" row per file, from the working-tree scan: numstat for tracked files, the line count
    # for new ones.
    changes = worktree_snapshot.working_tree_changes(repo_dir)
    rows = []
    for name in files:
        change = changes.get(name) or {"added": 0, "deleted": 0}
        rows.append(f"{name} | +{change['added']} -{change['deleted']}")
    return rows


def ticket_prefix(state):
    # The ticket id the plan folder or the branch carries, as the commit subject's prefix; "" when neither has one.
    plan_folder = pathlib.PurePosixPath(state["plan"]).parent.name if state.get("plan") else ""
    for name in (plan_folder, state.get("branch") or ""):
        found = TICKET_IN_NAME.search(name)
        if found:
            return found.group(1) + ": "
    return ""


PLAN_COMMIT_LINE = re.compile(r"^\W*Commit\b[\s:*]*`([^`]+)`", re.IGNORECASE)
EMPTY_SUMMARY = re.compile(r"none\b", re.IGNORECASE)


def planned_commit_subject(repo_dir, state):
    # The subject a `Commit `...`` line in the phase's own plan section names, or "" when the phase has none.
    plan_name = state.get("plan")
    phase_id = state.get("phase")
    if not plan_name or phase_id is None:
        return ""

    plan_path = pathlib.Path(repo_dir) / plan_name
    if not plan_path.is_file():
        return ""

    plan_lines = plan_path.read_text().splitlines()
    section = plan_format.phase_section(plan_lines, phase_id)
    if not section:
        return ""

    for line in plan_lines[section["start"]:section["end"]]:
        found = PLAN_COMMIT_LINE.match(line)
        if found:
            return found.group(1).strip()
    return ""


def spec_step_suffix(state, message):
    # " (phase A2)" for a plan run's phase, " (plan <folder>)" for a plan run with no phase; "" for a planless run or
    # a subject that already names the phase.
    if not state.get("plan"):
        return ""
    if state.get("phase") is None:
        return f" (plan {pathlib.PurePosixPath(state['plan']).parent.name})"

    phase_name = f"phase {state['phase']}"
    if phase_name.lower() in message.lower():
        return ""
    return f" ({phase_name})"


def commit_message(repo_dir, state):
    message = planned_commit_subject(repo_dir, state)
    if not message:
        recorded_behavior = state.get("behavior") or []
        summary = recorded_behavior[0].strip() if recorded_behavior else ""
        has_summary = bool(summary) and not EMPTY_SUMMARY.match(summary)
        message = summary if has_summary else (state.get("title") or "phase work")
        message += spec_step_suffix(state, message)

    prefix = ticket_prefix(state)
    if prefix and not message.lower().startswith(prefix.lower()):
        message = prefix + message
    return message


def phase_commit(repo_dir, state):
    # The phase's own changed files: dirty now, and either not dirty before the phase started or with content that
    # differs from the baseline hash. Files that were dirty before and are unchanged stay out of the command. The plan
    # is always in it when it changed: the script ticks the phase there. The commit names its files after `--`, so it
    # takes only those files from the index and leaves anything the user staged by hand staged and uncommitted.
    # Returns (text for the user, the commit command line, the files it commits); the text and line are "" with no
    # files.
    baseline = state.get("baseline") or {}
    rewrote_edited_by_check = sorted(set(state.get("checkRewroteEdited") or []))
    created_by_check = sorted(set(state.get("checkCreated") or []) - set(rewrote_edited_by_check))
    changed_by_check = sorted(set(state.get("checkChanged") or []) - set(rewrote_edited_by_check))
    left_by_check = {*created_by_check, *changed_by_check}
    dirty_now = {name: digest for name, digest in file_hashes(repo_dir).items() if name not in left_by_check}
    plan_name = state.get("plan")
    changed_since = [name for name in dirty_now if name in baseline and dirty_now[name] != baseline[name]]
    plan_had_earlier_edits = plan_name in changed_since
    own_files = [name for name in dirty_now if name not in baseline or name in changed_since]
    left_out = [name for name in dirty_now if name in baseline and name not in changed_since]
    edited_dirty = [name for name in changed_since if name != plan_name]
    if not own_files:
        return "", "", []

    check_changed_note = []
    if changed_by_check:
        quoted_changed = " ".join(shlex.quote(name) for name in changed_by_check)
        check_changed_note = [
            "Changed by the full check, not by the coder, and left out of the commit: " + ", ".join(changed_by_check),
            f"Restore them with: git checkout -- {quoted_changed}",
            "",
        ]

    check_rewrote_edited_note = []
    if rewrote_edited_by_check:
        check_rewrote_edited_note = [
            "Rewritten by the full check after the coder edited them, and kept in the commit: "
            + ", ".join(rewrote_edited_by_check),
            "Review their diff before you commit: they hold the coder's edits and the check's rewrite.",
            "",
        ]

    check_created_note = []
    if created_by_check:
        quoted_created = " ".join(shlex.quote(name) for name in created_by_check)
        check_created_note = [
            "Created by the full check, not by the coder, and left out of the commit: " + ", ".join(created_by_check),
            f"Delete them with: rm -- {quoted_created}",
            "",
        ]

    message = commit_message(repo_dir, state)
    quoted_files = " ".join(shlex.quote(name) for name in own_files)
    commit_line = f"git add -- {quoted_files} && git commit -m {shlex.quote(message)} -- {quoted_files}"
    lines = ["Files changed by this phase:", *diff_stat_rows(repo_dir, own_files), ""]
    if plan_had_earlier_edits:
        lines += [
            f"{plan_name} had uncommitted edits before the phase. The commit includes them with the phase tick.",
            "",
        ]
    if edited_dirty:
        lines += [
            "Edited by this phase, was dirty before (the commit mixes the earlier edits with this phase's): "
            + ", ".join(edited_dirty),
            "",
        ]
    if left_out:
        lines += ["Dirty before the phase and left out of the commit: " + ", ".join(left_out), ""]
    lines += check_changed_note
    lines += check_rewrote_edited_note
    lines += check_created_note
    lines += ["Commit command (not run by the script):", commit_line]
    return "\n".join(lines), commit_line, own_files


def finish_planless(repo_dir, state):
    state["stage"] = "done"
    save_state(repo_dir, state)
    commit_text, _, _ = phase_commit(repo_dir, state)
    if commit_text:
        say(repo_dir, commit_text)
    commit_note = " Nothing is committed: run the commit command above." if commit_text else ""
    emit("stop", f"Planless task reviewed.{commit_note} Tell the user the result.")


def load_finishing_plan(repo_dir, state):
    # (plan path, plan lines, plan, phase section) of the plan the finished phase belongs to, or None after a stop: the
    # plan file is gone, its Phase Status does not parse, or the phase moved to another ticket while the coder ran.
    plan_path = repo_dir / state["plan"]
    if not plan_path.is_file():
        return emit("stop", MISSING_PLAN_STOP.format(plan=state["plan"]))

    plan_lines = plan_path.read_text().splitlines()
    plan = plan_format.parse_plan_with_closing_phases(plan_lines)
    if plan["failures"]:
        return emit("stop", plan_format.plan_failure_message(plan, state["plan"]))

    number = state["phase"]
    running_entry = next((e for e in plan["entries"] if e["number"] == number), None)
    if running_entry and running_entry["moved"]:
        set_stop(state)
        save_state(repo_dir, state)
        return emit("stop", plan_format.moved_phase_stop(running_entry, state["plan"], coder_ran=True))

    section = plan_format.phase_text(plan_lines, number) if number is not None else "\n".join(plan_lines)
    return plan_path, plan_lines, plan, section or ""


def stop_for_unparsed_items(repo_dir, state, unparsed, ran_text):
    set_stop(state, "verification")
    save_state(repo_dir, state)
    if state.get("phase"):
        tick_text = (f" For a check that cannot be automated, the user can confirm it; on the user's word only, invoke "
                     f"Skill code with `tick {state['phase']}` to mark the phase done.")
    else:
        tick_text = (" For a check that cannot be automated, the user can confirm it and mark the phase done with "
                     "`tick`.")
    problem_lines = [f"- {line} - {verification_item_problem(line, repo_dir)}" for line in unparsed]
    emit("stop", f"The phase has Automated Verification items that could not be run ({ran_text}). Do not "
         "mark the phase done. Report each line to the user:", *problem_lines,
         VERIFICATION_ITEM_SHAPE + tick_text + " " + RESUME_LINE.format(noun="section", verb="verify"))


def save_verification_output(repo_dir, state, failed):
    # The full output of every failed command, in the run's folder. The path comes back.
    if not state.get("runId"):
        state["runId"] = script_utils.sortable_unique_id()
    output_file = run_file_path(repo_dir, state["runId"], VERIFICATION_OUTPUT_NAME)
    command_outputs = [(command, f"exit {code}", output) for command, code, output in failed]
    script_utils.write_command_outputs(output_file, command_outputs)
    return output_file


def verification_failure_lines(failed, errors_suffix=""):
    failure_lines = []
    for command, code, output in failed:
        quote = failing_test_quote(output, output[-400:], errors_suffix) or "(no output)"
        failure_lines.append(f"- `{command}` exit {code}: {quote}")
    return failure_lines


def stop_for_failed_commands(repo_dir, state, failed):
    output_file = save_verification_output(repo_dir, state, failed)
    set_stop(state, "verification")
    save_state(repo_dir, state)
    failure_lines = verification_failure_lines(failed, "\n(full output in the output file)")

    emit("stop", "Automated Verification failed. Do not mark the phase done. Report to the user:", *failure_lines,
         f"The full output of each failed command is in {output_file}; give that path to /debug.",
         RESUME_LINE.format(noun="failure", verb="verify"))


def run_phase_verification(repo_dir, state, section):
    # (results, skipped commands) of the phase's Automated Verification, or None after a stop. An item that yields no
    # command was not run: the phase is not verified, whatever the other items did.
    verify_results, skipped, unparsed = run_verification_commands(repo_dir, section)
    if unparsed:
        nothing_ran = not verify_results and not skipped
        ran_text = "nothing was run" if nothing_ran else f"{len(verify_results)} other command(s) ran"
        return stop_for_unparsed_items(repo_dir, state, unparsed, ran_text)

    failed = [(command, code, output) for command, code, output in verify_results if code != 0]
    if failed:
        return stop_for_failed_commands(repo_dir, state, failed)
    return verify_results, skipped


def not_run_label(tag):
    # An agent-run item is the session's to run, so its done line says who runs it; the other tags name only themselves.
    return f"{tag}, the session runs it" if tag == plan_format.AGENT_RUN_TAG else tag


def done_line_of(state, section, verify_results, skipped, reopened):
    # The one line that says what the phase's close ran.
    number = state["phase"]
    done_text = (f"Phase {number} marked done in {state['plan']}." if number is not None
                 else f"The plan {state['plan']} is finished.")
    listed_items = [line for _, line in plan_format.automated_verification_rows(section.splitlines())
                    if not plan_format.NO_AUTOMATED_CHECK.match(line)]
    if not verify_results and not skipped and not listed_items:
        done_line = f"{done_text} The phase lists no verification commands, so none were run."
    else:
        commands = "; ".join(c for c, _, _ in verify_results) or "none"
        done_line = (f"{done_text} Verification run: {len(verify_results)} command(s) green ({commands}); "
                     f"skipped as covered by the review loop: {len(skipped)}.")
        not_run_here = [f"not run here: {not_run_label(tag)} - {text[:120]}"
                        for tag, text in deferred_verification_items(section)]
        if not_run_here:
            done_line += " " + "; ".join(not_run_here) + "."
    if reopened:
        done_line += (f" Closing phase(s) {', '.join(reopened)} were checked and are unchecked again, so they run on "
                      "the new code.")
    return done_line


def announce_boundary(repo_dir, state, boundary):
    # What the user and the session see once the phase is closed. Block A auto-advances; B and C wait for the user.
    block, number = boundary["block"], state["phase"]
    done_line = boundary["done_line"]
    print(done_line)
    say(repo_dir, done_line)
    if boundary["deviation_text"]:
        say(repo_dir, boundary["deviation_text"])
    if boundary["commit_text"]:
        say(repo_dir, boundary["commit_text"])
    ledger_warning = script_utils.missing_ledger_warning()
    if ledger_warning:
        say(repo_dir, ledger_warning)

    if block == "A":
        next_start = f"{INSTALLED_COMMAND} {RESUME_VERB}"
        say(repo_dir, block_a(number, boundary["risk_label"], boundary["manual_groups"], boundary["next_number"]))
        commit_line = boundary["commit_line"]
        commit_step = f"First run this commit command as a Bash call: {commit_line}\nThen " if commit_line else ""
        emit("auto-advance", "The user sees block A at the end of the turn. "
             + f"{commit_step}in the same response run `{next_start}` for Phase " + boundary["next_number"] + ".")
        return

    block_text = block_b_or_c(block, number, boundary["risk_label"], state, boundary["manual_groups"],
                              boundary["next_number"], boundary["gate_block_message"], boundary["moved_text"])
    say(repo_dir, block_text.replace("<<STAGE QUEUE>>", "(the /stage queue is printed above in this turn)"))
    emit(
        "stop-block-" + block,
        "Invoke the Skill tool with `stage` and print its queue verbatim. The user sees the rest of the phase-complete "
        "block at the end of the turn: do not write it. Then wait for the user. When they say continue, run "
        f"`code_step.py {RESUME_VERB}`.",
    )


def adopted_deviation_text(plan_path, number, is_run_end):
    # The plan changes the code won without a question: this phase's at a phase end, every phase's at the run end.
    phase = None if is_run_end else number
    deviations = plan_format.below_criteria_deviations(plan_path.read_text(), phase)
    if not deviations:
        return ""

    scope = "this plan" if is_run_end else f"Phase {number}"
    heading = f"Plan deviations adopted in {scope} (the code won; no acceptance criterion changed):"
    return "\n".join([heading, *[f"- {line}" for line in deviations]])


def close_phase(repo_dir, state, plan_path, plan, section, manual_items, verification):
    # Ticks the phase in the plan, decides which boundary block the user sees, saves the done state and announces.
    number = state["phase"]
    reopened = []
    if number is not None:
        is_closing = any(e["number"] == number and e["closing"] for e in plan["entries"])
        plan_format.mark_phase_done(plan_path, number)
        reopened = [] if is_closing else plan_format.reopen_closing_phases(plan_path)

    entries = plan_format.parse_plan_with_closing_phases(plan_path.read_text().splitlines())["entries"]
    block, risk_label = boundary_decision(state, entries, number)
    gated_ahead, next_ungated = plan_format.gate_blockers(plan_format.ordered_pending(entries))
    commit_text, commit_line, commit_files = phase_commit(repo_dir, state)
    state["stage"] = "done"
    state["autoAdvance"] = block == "A"
    state["commitFiles"] = commit_files
    state["commitLine"] = commit_line
    clear_stop(state)
    save_state(repo_dir, state)

    verify_results, skipped = verification
    boundary = {
        "block": block, "risk_label": risk_label, "commit_text": commit_text, "commit_line": commit_line,
        "manual_groups": manual_groups_of(manual_items),
        "next_number": next_ungated["number"] if next_ungated else None,
        "gate_block_message": plan_format.gate_block_text(gated_ahead, next_ungated) if gated_ahead else "",
        "moved_text": plan_format.moved_phase_text(entries),
        "done_line": done_line_of(state, section, verify_results, skipped, reopened),
        "deviation_text": adopted_deviation_text(plan_path, number, block == "C")}
    announce_boundary(repo_dir, state, boundary)


def finish_phase(repo_dir, state, skip_verification=False, verification=None):
    # `verification` is the (results, skipped commands) of a passing Automated Verification run the caller already
    # made over the phase section, so the checks do not run twice.
    if not skip_verification and not mark_review_gate_clean(repo_dir, state):
        return

    if not state.get("plan"):
        return finish_planless(repo_dir, state)

    loaded = load_finishing_plan(repo_dir, state)
    if loaded is None:
        return
    plan_path, plan_lines, plan, section = loaded

    if skip_verification:
        verification = ([], [])
    elif verification is None:
        verification = run_phase_verification(repo_dir, state, section)
        if verification is None:
            return

    try:
        manual_items = plan_format.phase_manual_items(plan_lines, state["phase"], state["plan"])
    except plan_format.PlanFormatError as error:
        set_stop(state, "plan-format")
        save_state(repo_dir, state)
        return emit("stop", plan_format.manual_format_message(error, RESUME_LINE.format(noun="section", verb="verify")))

    close_phase(repo_dir, state, plan_path, plan, section, manual_items, verification)


# ---------- closing verbs ----------

def tick_plan_stop(repo_dir, state, args):
    # The stop text when `tick` has no plan run to act on, or None.
    if len(args) != 1:
        return VERB_USAGES["tick"].splitlines()[0]
    if state is None or not state.get("plan"):
        return "tick needs a plan run: there is no saved plan state. Run `start <plan>` first."

    plan_path = repo_dir / state["plan"]
    if not plan_path.is_file():
        return MISSING_PLAN_STOP.format(plan=state["plan"])

    plan = plan_format.parse_plan_with_closing_phases(plan_path.read_text().splitlines())
    if plan["failures"]:
        return plan_format.plan_failure_message(plan, state["plan"])
    return plan_format.phase_entry_stop(plan["entries"], args[0], state["plan"])


def stop_for_failed_tick_verification(number, failed):
    # The refusal when a command of the phase's Automated Verification fails at `tick`. Nothing is marked or saved.
    failure_lines = verification_failure_lines(failed)

    emit("stop", f"tick refused: Automated Verification of Phase {number} failed. Do not mark the phase done. "
         "Report to the user:", *failure_lines,
         "Fix the failure, or have the user correct the phase's Automated Verification line in the plan, then run "
         "`tick` again.")


def tick_verification_failures(repo_dir, state, number):
    # The failed (command, exit code, output) of the phase's Automated Verification commands, run now, and how many
    # commands ran. Whole-suite commands run too: after a stop or an abort nothing else ran the suite. An item that
    # names no command is left to the user, whose word `tick` is.
    section = current_phase_text(repo_dir, state["plan"], number) or ""
    verify_results, _, _ = run_verification_commands(repo_dir, section, run_whole_suites=True)
    failed = [(command, code, output) for command, code, output in verify_results if code != 0]
    return failed, len(verify_results)


def command_tick(args):
    # The user finished a phase outside /code. The main session runs this only on the user's word. A run stopped in
    # review, or dropped by `abort`, can still be ticked: the verification commands decide when the phase lists any;
    # otherwise the user's word does.
    repo_dir = repo_root_or_exit()
    os.chdir(repo_dir)
    live_state = load_state(repo_dir)
    state = live_state or load_aborted_plan_state(repo_dir)
    has_one_phase_arg = live_state is not None and live_state.get("plan") and len(args) == 1
    if has_one_phase_arg and stop_while_plan_edit_coder_is_out(repo_dir, state, "tick " + " ".join(args)):
        return

    stop_text = tick_plan_stop(repo_dir, state, args)
    if stop_text:
        return emit("stop", stop_text)

    number = args[0]
    failed, commands_run = tick_verification_failures(repo_dir, state, number)
    if failed:
        return stop_for_failed_tick_verification(number, failed)

    criteria_message = settle_criteria_guard(repo_dir, state, branch_label(repo_dir))
    if criteria_message:
        say(repo_dir, criteria_message)

    plan_path = repo_dir / state["plan"]
    plan_format.mark_phase_done(plan_path, number)
    if commands_run:
        verification_note = f"its {commands_run} Automated Verification command(s) passed at `tick`."
        scope_note = "outside the coder and review steps of /code"
    else:
        verification_note = "no Automated Verification command ran at `tick`."
        scope_note = "outside the coder, review and verification steps of /code"
    plan_format.append_deviation(plan_path, [f"- {time.strftime('%Y-%m-%d')} (Phase {number}): marked done with "
                                             f"`tick`, {scope_note}; {verification_note}"])
    clear_stop(state)
    state.update({"stage": "done", "phase": number, "autoAdvance": False, "commitFiles": [], "commitLine": ""})
    state.pop("dispatchAt", None)
    save_state(repo_dir, state)
    emit("stop", f"Phase {number} is marked done in {state['plan']}. Run `resume` for the next phase when the user "
         "asks.")


def command_verify(repo_dir, state, args):
    # The user's fix of the plan's verification lines is the phase text from here on, so a later stop does not call it
    # stale.
    if state.get("plan") and state.get("phase") is not None:
        with contextlib.suppress(OSError):
            state["phaseText"] = current_phase_text(repo_dir, state["plan"], state["phase"])

    finish_phase(repo_dir, state)
