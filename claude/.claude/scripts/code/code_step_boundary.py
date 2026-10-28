"""code_step_boundary.py: the part of code_step.py that guards the plan's acceptance criteria and ends a phase: the
saved criteria copy, the Automated Verification runner, the phase boundary and the closing verbs (skill-done, tick,
verify).

Imports run one way: code_step_core, code_step_boundary, code_step_hooks, code_step_gates, code_step_start,
code_step_report, code_step_review, code_step. The phase-end block text is in code_step_phase_end."""
import datetime
import os
import pathlib
import re
import shlex
import shutil
import time

import plan_format
import reviewed_tree
import script_utils
from code_step_concentration import (
    concentration_gate_position,
    manual_gate_item_end,
    missing_gate_item_lines,
    with_manual_gate_lines,
)
from code_step_core import (
    INSTALLED_COMMAND,
    RESUME_LINE,
    RESUME_VERB,
    SCRIPTS_DIR,
    branch_label,
    emit,
    file_hashes,
    is_dispatch_open,
    load_handback,
    load_state,
    repo_root_or_exit,
    run_session_id,
    save_state,
    say,
    script_command,
    session_pin,
)
from code_step_phase_end import block_a, block_b_or_c, manual_groups_of
from script_utils import git_output, run_command
from test_run_output import matches_no_test

VERIFY_TIMEOUT_SECONDS = 600
# A filtered test run that exits 0 but reports no passed test did not run the phase's test: it fails the box.
NO_TEST_MATCHED_EXIT_CODE = 1
NO_TEST_MATCHED_NOTE = "\nthe test filter matched no test: the run exits 0 but reports no passed test\n"
# An rg, grep or git grep line is a ban (exit 1, no match, holds it) unless its text, outside the command, says it
# checks presence (exit 0 passes). Ban wording on the same line wins. A search wrapped in another command, such as
# `test -n "$(git grep ...)"`, is judged by its own exit code.
SEARCH_COMMAND = re.compile(r"^(?:rg|grep|egrep|git grep)\s")
BAN_WORDING = re.compile(r"\bprohibition\b|\bno\s+(?:match(?:es)?|output|hits?)\b|\bprints?\s+nothing\b"
                         r"|\bexit(?:s|ing)?\s+(?:code\s+)?1\b|\babsent\b|\bmust\s+not\b|\bnone\b|\bnothing\b"
                         r"|\bgone\b|\bremoved\b|\bzero\b|\bno\s+longer\b",
                         re.IGNORECASE)
PRESENCE_WORDING = re.compile(r"\bpresence\b|\bpresent\b|\bexists?\b|\bcontains?\b|\bdefines?\b|\bdefined\b"
                              r"|\bfinds?\b|\bfound\b|\ba\s+hit\b|\bmatches\b", re.IGNORECASE)
SEARCH_BAN_NOTE = ("\nan rg, grep or git grep line is a ban unless its text says it checks presence "
                   "(present, exists, contains, finds)\n")
# A ban written `! rg ...` is the same ban as `rg ...`: no match holds it.
# A leading `cd <dir> &&` does not change what the command searches: it stays in the command and is ignored here.
LEADING_CD = r"(?:cd \S+ && )?"
NEGATED_SEARCH = re.compile(r"^(" + LEADING_CD + r")!\s+(?=(?:rg|grep|egrep|git grep)\s)")


def without_negation(span):
    """The span with the `!` of a negated search taken off, any leading `cd <dir> &&` kept."""
    return NEGATED_SEARCH.sub(r"\1", span)


def without_leading_cd_and_env(command):
    """The command with any NAME=value words and a `cd <dir> &&` it starts with taken off, for judging what it is."""
    unassigned = script_utils.without_leading_env_assignments(command)
    return re.sub(r"^cd \S+ && ", "", unassigned)
WHOLE_SUITE = re.compile(r"^(?:(?:cd \S+ && )?(?:npm|pnpm|yarn) (?:run )?(?:test|lint)"
                         r"|(?:cd \S+ && )?npx (?:vitest|jest)(?: run)?|(?:python3 -m )?pytest|ruff check)$")
TICKET_IN_NAME = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Z0-9]+-\d+)(?![A-Za-z0-9])")
COMMAND_START = re.compile(r"^(?:" + script_utils.ENV_PREFIX.pattern + r")?"
                           r"(cd |npm |npx |pnpm |yarn |git |node |python3? |pytest|ruff |bash |curl |make "
                           r"|cargo |go |deno |bun |uv |poetry |tsc\b|eslint |vitest|jest|mvn |gradle |\./"
                           r"|dotnet |docker |just |rake |bundle |ruby |php |composer |mix |swift |sbt |bazel |tox\b"
                           r"|mypy |pyright|sh )")
# Programs that a prose span can start with but that are never a check: they start a session, never end or wait for
# input. `tail` is one only when it follows a file (see TAIL_FOLLOWS).
NOT_A_CHECK_PROGRAMS = ("claude", "yes", "watch", "top", "htop", "less", "more", "vi", "vim", "nano", "sleep")
TAIL_FOLLOWS = re.compile(r"^(?:-[A-Za-z0-9]*[fF][A-Za-z0-9]*|--follow(?:=\w+)?)$")
VERIFICATION_ITEM_SHAPE = (
    "Each Automated Verification item is one line in one of three shapes. (1) One backticked command that starts with "
    "a program on PATH (with at least one argument) or an executable file in the repo, for example the line "
    "'- [ ] **Name**: what it checks - `npm test`'. A check that needs a variable assignment, `&&`, a pipe or a "
    "subshell goes in an executable repo script, run as `path/to/script args`; the script's comments name no ticket "
    "or plan path. (2) N/A, for example '- [ ] N/A - docs only'. (3) A tag that "
    "says CI or a person runs it, for example '- [ ] **CI-verified**: the pipeline runs it' or '- [ ] Human-only: "
    "look at the page'. This script never runs the third shape.")


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
    found = git_output(repo_dir, "rev-parse", "--path-format=absolute", "--git-path", "code-step-replaced-criteria")
    folder = pathlib.Path(found)
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


# ---------- verification runner ----------

def deferred_verification_items(phase_section):
    # (tag, item text) for each Automated Verification item the plan leaves to CI or to a person, in file order.
    deferred = []
    for _, line in plan_format.automated_verification_rows(phase_section.splitlines()):
        tag = plan_format.deferred_verification_tag(line)
        if not tag:
            continue

        item_text = plan_format.automated_item_text(line)
        deferred.append((tag, item_text))
    return deferred


def never_returns(words):
    # True when the command in `words` is a program that never ends or waits for input, so it cannot be a check.
    program_name = pathlib.PurePath(words[0]).name
    if program_name in NOT_A_CHECK_PROGRAMS:
        return True

    return program_name == "tail" and any(TAIL_FOLLOWS.match(word) for word in words[1:])


def starts_like_a_program_here(span, repo_dir):
    # A span COMMAND_START does not know is a command when it starts with a path to an executable file of the repo,
    # or with a program on PATH that has at least one argument after it (a program word alone is how prose names a
    # tool, and a bare word is looked up on PATH only, never in the repo).
    words = script_utils.without_leading_env_assignments(span).split()
    if not words:
        return False

    program = words[0]
    has_slash = "/" in program
    if has_slash and repo_dir is not None and script_utils.is_executable_file_inside(repo_dir, program):
        return True

    if len(words) < 2 or never_returns(words):
        return False

    # A relative path with a slash is looked up from the working directory, not PATH: only the repo-file rule above
    # may accept it, and that rule keeps it inside the repo.
    if has_slash and not pathlib.PurePath(program).is_absolute():
        return False

    return shutil.which(program) is not None


def verification_command(line, repo_dir=None):
    # The first backticked span that starts with a known program, after any leading NAME=value assignments, which the
    # shell passes to the command; when none does, the first span that starts with a program of this machine. The
    # line may continue after it ("`npm run build` exits 0.").
    spans = [without_negation(span) for span in script_utils.backticked_spans(line)]
    for span in spans:
        if COMMAND_START.match(span):
            return span

    for span in spans:
        if starts_like_a_program_here(span, repo_dir):
            return span

    return None


def verification_item_problem(line, repo_dir):
    # Why an Automated Verification item cannot run, or None when it runs, says there is nothing to run or is left to
    # CI or a person. The write-time check of a plan and the stop after a phase use this one reading.
    if plan_format.runs_no_command(line):
        return None
    if verification_command(line, repo_dir):
        return None

    spans = script_utils.backticked_spans(line)
    if not spans:
        return "it has no backticked command and is not marked N/A, CI-verified or human-only"

    start_words = []
    for span in spans:
        first_word = script_utils.first_command_word(span) or span
        start_words.append(f"`{first_word}`")
    return ("no backticked span starts with a program on PATH (with an argument) or an executable file in the repo "
            f"(it starts with {', '.join(start_words)})")


def phase_verification_rows(plan_lines, section, closing, plan_name):
    # (index, line) of the checkbox items to check in one phase section, indexes relative to the section. A closing
    # phase has no Automated Verification heading, so every checkbox line in it counts.
    section_lines = plan_lines[section["start"]:section["end"]]
    if closing:
        return [(index, line) for index, line in enumerate(section_lines) if plan_format.AUTOMATED_ITEM.match(line)]
    return plan_format.automated_verification_rows(section_lines, plan_name, section["start"] + 1, strict=True)


def verification_format_failure(plan_lines, plan_name, repo_dir, entries):
    # The write-time message for open phases whose Automated Verification items cannot run, or None when all can. A
    # closing phase is checked by its skill, which runs no verification command, so only its boxes that diff a moving
    # branch name are reported.
    problems = []
    for entry in entries:
        if not entry["open"]:
            continue

        section = plan_format.phase_section(plan_lines, entry["number"])
        if section is None:
            continue

        try:
            rows = phase_verification_rows(plan_lines, section, entry["closing"], plan_name)
        except plan_format.PlanFormatError as error:
            problems.append(str(error))
            continue

        for index, line in rows:
            problem = None
            if plan_format.moving_base_diff(line):
                problem = plan_format.MOVING_BASE_DIFF_FIX
            elif not entry["closing"]:
                problem = verification_item_problem(line, repo_dir)
            if problem:
                problems.append(f"{plan_name}:{section['start'] + index + 1}: Phase {entry['number']}: "
                                f"{line.strip()[:100]} - {problem}")

    if not problems:
        return None

    return ("The plan has Automated Verification items that cannot run. Every open phase is checked at each start, "
            "so a later phase's line stops the first phase's start. Fix each line:\n" + "\n".join(problems) + "\n"
            + VERIFICATION_ITEM_SHAPE)


def is_search_ban(command, line):
    if not SEARCH_COMMAND.match(without_leading_cd_and_env(command)):
        return False

    if any(without_negation(span) == command and span != command for span in script_utils.backticked_spans(line)):
        return True

    text = line.replace(command, "")
    if BAN_WORDING.search(text):
        return True

    return not PRESENCE_WORDING.search(text)


def check_prohibition(repo_dir, command, code, output):
    # A git grep, rg or grep ban passes on exit 1 (no match) and fails on exit 0 (a hit). Any other exit is an error
    # that stops.
    # A pipe form is judged by its output: empty or 0 passes.
    hit_rows = len([row for row in output.splitlines() if row.strip()])
    if "|" in command:
        verdict = 0 if output.strip() in ("", "0") else 1
        hits = 0 if verdict == 0 else int(output) if output.strip().isdigit() else hit_rows
    elif code == 1:
        verdict, hits = 0, 0
    elif code == 0:
        verdict, hits = 1, hit_rows
    else:
        verdict, hits = code, 0
    run_command(["bash", str(SCRIPTS_DIR / "telemetry" / "log-scan"), f"repo={repo_dir.name}", "scan=prohibition",
                 "stage=code-phase", f"exit={verdict}", f"candidates={hits}", f"confirmed={hits}",
                 f"branch={branch_label(repo_dir)}", f"note={command[:120]}"], repo_dir)
    return command, verdict, output


def run_verification_commands(repo_dir, phase_section):
    results = []
    skipped = []
    unparsed = []
    timeout = int(os.environ.get("CODE_STEP_VERIFY_TIMEOUT", VERIFY_TIMEOUT_SECONDS))
    for _, line in plan_format.automated_verification_rows(phase_section.splitlines()):
        if plan_format.runs_no_command(line):
            continue
        command = verification_command(line, repo_dir)
        if command is None:
            unparsed.append(line.strip())
            continue
        if WHOLE_SUITE.match(script_utils.without_leading_env_assignments(command)):
            skipped.append(command)
            continue
        code, output = run_command(command, repo_dir, timeout=timeout)
        if is_search_ban(command, line):
            result = check_prohibition(repo_dir, command, code, output)
            if result[1] != 0 and not PRESENCE_WORDING.search(line.replace(command, "")):
                result = (result[0], result[1], result[2] + SEARCH_BAN_NOTE)
            results.append(result)
            continue
        if matches_no_test(command, code, output):
            code = NO_TEST_MATCHED_EXIT_CODE
            output += NO_TEST_MATCHED_NOTE
        results.append((command, code, output))
    return results, skipped, unparsed


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
    # The review-commit-gate hook reads this file: the review loop ended clean, so the session may commit.
    # Returns False after emitting a stop when the hand-back record shows the loop did not end clean, or when the
    # shared hand-back reader is not installed. Nothing is written then. The hand-back is read for the session the
    # run is pinned to, which launched the review loop; the mark is written for the session that commits.
    module, import_error = load_handback()
    if module is None:
        emit("stop", f"Cannot confirm the review loop ended clean: {import_error}. The review gate is not marked "
             "clean. Tell the user.")
        return False
    # The packet this run read is the record of how its loop ended. The shared hand-back store is keyed by session
    # and can hold an earlier converged hand-back, so it never overrules a packet that did not converge.
    review_status = state.get("reviewStatus")
    if review_status is not None and review_status not in module.CLEAN_STATUSES:
        state["stage"] = "stopped"
        state["stopReason"] = "review-not-converged"
        save_state(repo_dir, state)
        emit("stop", f"The phase stays open: its review loop ended {review_status}, not converged. Nothing is "
             "committed and the review gate is not marked clean. Report to the user what the review waits on.")
        return False
    reviewing_session = run_session_id(state)
    reason = module.false_clean_reason(reviewing_session)
    if reason:
        state["stage"] = "stopped"
        state["stopReason"] = "false-clean"
        save_state(repo_dir, state)
        emit("stop", f"The review gate is not marked clean: {reason}. Nothing is committed.",
             "To review the same diff again, invoke Skill code with `review-again`.")
        return False
    gate_dir = pathlib.Path.home() / ".claude" / "state" / "review-gate"
    gate_dir.mkdir(parents=True, exist_ok=True)
    committing_session = session_pin() or state.get("sessionId") or "unknown"
    (gate_dir / committing_session).write_text("clean\n")
    # The tree the loop reviewed: a later coder dispatch that edits nothing leaves it unchanged, so its commit passes.
    reviewed_tree.record_reviewed(committing_session, repo_dir)
    return True


def count_lines(path):
    try:
        return len(path.read_text(errors="replace").splitlines())
    except OSError:
        return 0


def diff_stat_rows(repo_dir, files):
    # One "path | +added -deleted" row per file: git's numstat for tracked files, the line count for new ones.
    numstat = {}
    for row in (git_output(repo_dir, "diff", "--numstat", "HEAD", "--", *files) or "").splitlines():
        added, deleted, name = row.split("\t", 2)
        numstat[name] = (added, deleted)
    rows = []
    for name in files:
        added, deleted = numstat.get(name) or (str(count_lines(repo_dir / name)), "0")
        rows.append(f"{name} | +{added} -{deleted}")
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


def commit_message(repo_dir, state):
    message = planned_commit_subject(repo_dir, state)
    if not message:
        recorded_behavior = state.get("behavior") or []
        summary = recorded_behavior[0].strip() if recorded_behavior else ""
        has_summary = bool(summary) and not EMPTY_SUMMARY.match(summary)
        message = summary if has_summary else (state.get("title") or "phase work")
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
    dirty_now = file_hashes(repo_dir)
    plan_name = state.get("plan")
    changed_since = [name for name in dirty_now if name in baseline and dirty_now[name] != baseline[name]]
    plan_had_earlier_edits = plan_name in changed_since
    own_files = [name for name in dirty_now if name not in baseline or name in changed_since]
    left_out = [name for name in dirty_now if name in baseline and name not in changed_since]
    edited_dirty = [name for name in changed_since if name != plan_name]
    if not own_files:
        return "", "", []

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
        return emit("stop", f"The plan file {state['plan']} is missing (a branch switch?). Tell the user.")

    plan_lines = plan_path.read_text().splitlines()
    plan = plan_format.parse_plan_with_closing_phases(plan_lines)
    if plan["failures"]:
        return emit("stop", plan_format.plan_failure_message(plan, state["plan"]))

    number = state["phase"]
    running_entry = next((e for e in plan["entries"] if e["number"] == number), None)
    if running_entry and running_entry["moved"]:
        state["stage"] = "stopped"
        state.pop("stopReason", None)
        save_state(repo_dir, state)
        return emit("stop", plan_format.moved_phase_stop(running_entry, state["plan"], coder_ran=True))

    section = plan_format.phase_text(plan_lines, number) if number is not None else "\n".join(plan_lines)
    return plan_path, plan_lines, plan, section or ""


def stop_for_unparsed_items(repo_dir, state, unparsed, ran_text):
    state.update({"stage": "stopped", "stopReason": "verification"})
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


def stop_for_failed_commands(repo_dir, state, failed):
    state.update({"stage": "stopped", "stopReason": "verification"})
    save_state(repo_dir, state)
    failure_lines = [f"- `{command}` exit {code}: {output[-400:]}" for command, code, output in failed]
    emit("stop", "Automated Verification failed. Do not mark the phase done. Report to the user:", *failure_lines,
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
        not_run_here = [f"not run here: {tag} - {text[:120]}" for tag, text in deferred_verification_items(section)]
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
    state.pop("stopReason", None)
    save_state(repo_dir, state)

    verify_results, skipped = verification
    boundary = {
        "block": block, "risk_label": risk_label, "commit_text": commit_text, "commit_line": commit_line,
        "manual_groups": manual_groups_of(manual_items),
        "next_number": next_ungated["number"] if next_ungated else None,
        "gate_block_message": plan_format.gate_block_text(gated_ahead, next_ungated) if gated_ahead else "",
        "moved_text": plan_format.moved_phase_text(entries),
        "done_line": done_line_of(state, section, verify_results, skipped, reopened)}
    announce_boundary(repo_dir, state, boundary)


def finish_phase(repo_dir, state, skip_verification=False):
    if not skip_verification and not mark_review_gate_clean(repo_dir, state):
        return

    if not state.get("plan"):
        return finish_planless(repo_dir, state)

    loaded = load_finishing_plan(repo_dir, state)
    if loaded is None:
        return
    plan_path, plan_lines, plan, section = loaded

    verification = ([], [])
    if not skip_verification:
        verification = run_phase_verification(repo_dir, state, section)
        if verification is None:
            return

    try:
        manual_items = plan_format.phase_manual_items(plan_lines, state["phase"], state["plan"])
    except plan_format.PlanFormatError as error:
        state.update({"stage": "stopped", "stopReason": "plan-format"})
        save_state(repo_dir, state)
        return emit("stop", plan_format.manual_format_message(error, RESUME_LINE.format(noun="section", verb="verify")))

    close_phase(repo_dir, state, plan_path, plan, section, manual_items, verification)


# ---------- closing verbs ----------

def evidence_command_shape(item_count):
    # The `skill-done pass` line with one `--evidence` placeholder per open item.
    placeholders = " ".join(f'--evidence "<item {number} evidence>"' for number in range(1, item_count + 1))
    return script_command(f"skill-done pass {placeholders}")


def evidence_request_lines(items):
    # What the session records at `skill-done pass`: each open Success Criteria item, numbered, and the command.
    if not items:
        return []
    numbered_items = [f"{number}. {item['text']}" for number, item in enumerate(items, 1)]
    return [
        "Open Success Criteria items. Give one `--evidence` per item, in this order; the script checks each box and "
        "writes the evidence under it:",
        *numbered_items,
        f"Run `{evidence_command_shape(len(items))}`. Each evidence states what its item asks for, with the numbers "
        "where it asks for counts (for example both concentration-gate counts, the test-audit denominator).",
    ]


def phase_open_items(plan_lines, number):
    # The open Success Criteria items of one phase's section, and the section's first line index in the plan.
    section = plan_format.phase_section(plan_lines, number)
    if section is None:
        return [], 0
    return plan_format.open_success_items(plan_lines[section["start"]:section["end"]]), section["start"]


def with_simplify_lines(items, evidence, simplify_done_texts):
    # `evidence` with each given Done text added as a Done line under the concentration-gate item's evidence.
    if not simplify_done_texts:
        return evidence

    simplify_lines = [f"\n  - Done: {text}" for text in simplify_done_texts]

    gate_position = concentration_gate_position(items)
    combined = list(evidence)
    combined[gate_position] += "".join(simplify_lines)
    return combined


def stop_for_missing_gate_item(items, simplify_done_texts, rerun_command):
    # Emits a stop and returns True when a simplify record has no open concentration-gate item to be written under.
    # `rerun_command` is the refused `skill-done pass` when the gate triggered, else None.
    if not simplify_done_texts or concentration_gate_position(items) is not None:
        return False

    emit("stop", *missing_gate_item_lines(rerun_command))
    return True


def record_closing_evidence(repo_dir, state, evidence, simplify_done_texts, rerun_command):
    # Writes each open item's evidence into the plan, and the simplify Done texts under the concentration-gate item.
    # Returns False, after a stop, when the evidence count does not match the open items or a simplify record has no
    # open concentration-gate item; nothing is written then.
    plan_path = repo_dir / state["plan"]
    if not plan_path.is_file():
        return True

    plan_lines = plan_path.read_text().split("\n")
    items, offset = phase_open_items(plan_lines, state["phase"])

    manual_gate_end = None
    if simplify_done_texts and concentration_gate_position(items) is None:
        manual_gate_end = manual_gate_item_end(plan_lines, state["phase"])
    if manual_gate_end is None and stop_for_missing_gate_item(items, simplify_done_texts, rerun_command):
        return False

    if len(items) != len(evidence):
        listing = evidence_request_lines(items) or ["The phase has no open Success Criteria items: run "
                                                    "`skill-done pass` with no `--evidence`."]
        emit("stop", f"skill-done pass got {len(evidence)} --evidence values for {len(items)} open items. Nothing "
             "was changed.", *listing)
        return False

    shifted = [{**item, "index": item["index"] + offset, "end": item["end"] + offset} for item in items]
    if manual_gate_end is not None:
        plan_lines, shifted = with_manual_gate_lines(plan_lines, shifted, manual_gate_end, simplify_done_texts)
        simplify_done_texts = ()
    if not items and manual_gate_end is None:
        return True

    recorded = with_simplify_lines(items, evidence, simplify_done_texts)
    plan_path.write_text("\n".join(plan_format.write_item_evidence(plan_lines, shifted, recorded)))
    return True


def command_skill_done(repo_dir, state, args, simplify_done_texts=(), rerun_command=None):
    words, evidence = script_utils.pop_repeated_option(args, "--evidence")
    verdict = words[0].lower() if words else "pass"
    if verdict not in ("pass", "fail"):
        return emit("stop", "skill-done takes pass or fail.")
    if verdict == "fail":
        state["stage"] = "stopped"
        save_state(repo_dir, state)
        return emit("stop", "The closing phase's check failed (a MISSING criterion, or an unmet Success Criteria). "
                    "Do not mark the phase done. Report what failed to the user.")
    if not record_closing_evidence(repo_dir, state, evidence, simplify_done_texts, rerun_command):
        return
    finish_phase(repo_dir, state, skip_verification=True)


def tick_entry_stop(state, plan, number):
    # The stop text when the phase cannot be ticked, or None when it can.
    entry = next((e for e in plan["entries"] if e["number"] == number), None)
    if entry is None:
        listed = ", ".join(e["number"] for e in plan["entries"]) or "none"
        return f"Phase {number} is not in the Phase Status of {state['plan']}. Listed phases: {listed}."
    if entry["moved"]:
        return plan_format.moved_phase_stop(entry, state["plan"])
    if entry["done"]:
        return f"Phase {number} is already marked done in {state['plan']}."
    return None


def tick_plan_stop(repo_dir, state, args):
    # The stop text when `tick` has no plan run to act on, or None.
    if len(args) != 1:
        return "usage: code_step.py tick <phase id>"
    if state is None or not state.get("plan"):
        return "tick needs a plan run: there is no saved plan state. Run `start <plan>` first."

    plan_path = repo_dir / state["plan"]
    if not plan_path.is_file():
        return f"The plan file {state['plan']} is missing (a branch switch?). Tell the user."

    plan = plan_format.parse_plan_with_closing_phases(plan_path.read_text().splitlines())
    if plan["failures"]:
        return plan_format.plan_failure_message(plan, state["plan"])
    return tick_entry_stop(state, plan, args[0])


def command_tick(args):
    # The user finished a phase outside /code. The main session runs this only on the user's word.
    repo_dir = repo_root_or_exit()
    os.chdir(repo_dir)
    state = load_state(repo_dir)
    has_one_phase_arg = state is not None and state.get("plan") and len(args) == 1
    if has_one_phase_arg and stop_while_plan_edit_coder_is_out(repo_dir, state, "tick " + " ".join(args)):
        return

    stop_text = tick_plan_stop(repo_dir, state, args)
    if stop_text:
        return emit("stop", stop_text)

    number = args[0]
    criteria_message = settle_criteria_guard(repo_dir, state, branch_label(repo_dir))
    if criteria_message:
        say(repo_dir, criteria_message)

    plan_path = repo_dir / state["plan"]
    plan_format.mark_phase_done(plan_path, number)
    plan_format.append_deviation(plan_path, [f"- {time.strftime('%Y-%m-%d')} (Phase {number}): marked done with "
                                             "`tick`, outside the coder, review and verification steps of /code."])
    state.update({"stage": "done", "phase": number, "autoAdvance": False, "commitFiles": [], "commitLine": ""})
    state.pop("dispatchAt", None)
    save_state(repo_dir, state)
    emit("stop", f"Phase {number} is marked done in {state['plan']}. Run `resume` for the next phase when the user "
         "asks.")


def command_verify(repo_dir, state, args):
    finish_phase(repo_dir, state)
