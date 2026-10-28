"""The start verb of code_step: argument parsing, plan and phase choice, and the first coder dispatch."""
import collections
import os
import pathlib
import re
import shlex
import sys
import time

import plan_format
import script_utils
from code_step_boundary import (
    criteria_rel,
    evidence_command_shape,
    evidence_request_lines,
    settle_criteria_guard,
    stop_while_plan_edit_coder_is_out,
    verification_format_failure,
)
from code_step_concentration import REFACTOR_SKILL, concentration_gate, gate_lines, simplify_option
from code_step_core import (
    INSTALLED_COMMAND,
    RESUME_LINE,
    RESUME_VERB,
    SCRIPTS_DIR,
    TICKET_ID,
    abandon_open_dispatch,
    ask_user,
    branch_label,
    clear_say,
    emit,
    emit_dispatch,
    file_hashes,
    head_commit,
    is_run_open,
    load_state,
    open_dispatch,
    refuse,
    repo_root_or_exit,
    ruled_asks_lines,
    ruled_asks_path,
    save_state,
    say,
    script_command,
    session_pin,
    stale_phase_reason,
    start_run,
    uncommitted_files,
)
from code_step_gates import derive_gate_commands
from code_step_report import ENG_SPEC_BRIEF
from code_step_restart import drop_open_run, reopens_stopped_run
from code_step_start_args import (
    START_MODIFIERS,
    RepoFlagError,
    TaskFileError,
    absolute_path_args,
    carry_run_notes,
    is_flag,
    outside_repo_plan_refusal,
    read_task_file,
    run_notes_lines,
    split_plan_words,
    split_quoted_flags,
    start_repo_path,
    starts_task_text,
)
from script_utils import run_command

START_USAGE = ('usage: code_step.py start [--repo <path>] [<plan>] [+fast|+deep] [--phase <id>] [--restart] '
               '[--headless] [<run notes>]\n'
               '       code_step.py start [--repo <path>] --task "<task text>"\n'
               '       code_step.py start [--repo <path>] --task-file <path>\n'
               '--phase <id> starts the named phase; the text after a plan file or ticket id and its phase is the '
               "run notes: the coder's constraints for that run. Text that comes first, when there is no plan file, "
               'ticket id or directory, is the task text. --task-file reads the task text from a file, as it is. A '
               'flag before the text, or after a plan, must be known. --restart drops an unfinished run and starts '
               'over. With --restart, text that comes first becomes the run notes of the saved plan when that plan '
               'has open phases; use --task for planless work after --restart. --repo runs everything in that '
               'checkout, not the current directory; so does a `Repo: <path>` or `Repo root: <path>` first line in '
               'the task file. --headless is for a run no person watches: a phase that would wait for sign-off '
               'commits and goes on to the next phase.')
FOLLOW_UP_HINT = ("A follow-up change to a finished plan needs the task text: invoke Skill code with "
                  "`start --task \"<text>\"`.")
# The verbs that older printed commands still name. Each one now does what `resume` does.
RESUME_ALIASES = ("after-coder", "after-review", "after-plan-edit")
VERB_WORDS_REPLACED_BY_RESUME = ("continue", "resume", *RESUME_ALIASES)
VERB_WORDS_THAT_CARRY_INPUT = ("review-again", "decide", "asks-done", "skill-done", "tick", "verify")


def usage_error(message):
    print(f"code_step.py start: {message}\n{START_USAGE}", file=sys.stderr)
    sys.exit(2)


StartArgs = collections.namedtuple("StartArgs", "modifier plan_args task_text phase_id restart positional_words "
                                   "run_notes headless", defaults=(None, False))


def phase_flag_value(args, position):
    # The id after `--phase`; a missing id, or a flag in its place, exits 2.
    if position + 1 >= len(args) or args[position + 1].startswith("-"):
        usage_error("--phase needs a phase id")
    return args[position + 1]


def reject_unknown_flag(word):
    # --restart and --headless are the flags besides --phase, --task, --task-file and --repo. --help prints usage and
    # exits 0 before any state is touched; any other flag exits 2.
    if word in script_utils.USAGE_WORDS:
        print(START_USAGE)
        sys.exit(0)
    if word not in ("--restart", "--headless"):
        usage_error(f"unknown flag {word}")


def task_file_text(args, flag_position):
    try:
        return read_task_file(args, flag_position)
    except TaskFileError as error:
        usage_error(str(error))


def parse_start_args(args):
    # Flags are read left to right up to the first word that is not a plan file, ticket id or directory: that word
    # and everything after it is task text, as is everything after --task. --task-file takes the task text from the
    # file it names. positional_words holds the words of task text that did not follow --task (None otherwise):
    # start_refusal reads them.
    modifiers = []
    plan_args = []
    task_text = None
    positional_words = None
    phase_id = None
    switches = set()
    position = 0
    while position < len(args):
        word = args[position]
        if word == "--task":
            task_text = " ".join(args[position + 1:])
            break
        if task_text is not None and starts_task_text(word):
            usage_error("text after --task-file")
        if word == "--task-file":
            task_text = task_file_text(args, position)
            position += 2
            continue
        if word == "--phase":
            phase_id = phase_flag_value(args, position)
            position += 2
            continue
        if word == "--repo":
            position += 2
            continue
        if starts_task_text(word):
            positional_words = args[position:]
            task_text = " ".join(positional_words)
            break

        if word in START_MODIFIERS:
            modifiers.append(word)
        elif is_flag(word):
            reject_unknown_flag(word)
            switches.add(word)
        else:
            plan_args.append(word)
        position += 1
    modifier = "+deep" if "+deep" in modifiers else "+fast" if modifiers else None
    return StartArgs(modifier, plan_args, task_text, phase_id, "--restart" in switches, positional_words,
                     headless="--headless" in switches)


def phase_label(state):
    plan_name = state.get("plan") or "a task with no plan"
    return f"Phase {state['phase']} of {plan_name}" if state.get("phase") is not None else plan_name


def phase_words_as_flag(args):
    # `<plan> Phase <id>` and `<plan> <id>` name a phase of that plan: the words with `--phase <id>` in their place.
    # Any other args come back as they were.
    words = script_utils.words_of_arguments(args) if args else []
    if "--task" in words or "--task-file" in words or "--phase" in words:
        return args

    has_phase_word = len(words) >= 3 and words[-2].lower() == "phase"
    plan_at = len(words) - (3 if has_phase_word else 2)
    if plan_at < 0 or not re.fullmatch(plan_format.PHASE_ID, words[-1]):
        return args

    plan_word = words[plan_at]
    if not (plan_word.endswith(".md") and os.path.isfile(plan_word)):
        return args
    return [*words[:plan_at + 1], "--phase", words[-1]]


def first_word_is_verb(words):
    # Whether `start` was given a verb name in place of task text. `start`, `status` and `abort` are verbs only where
    # a verb would fit: `status` or `abort` alone, and `start` alone or before a flag or a modifier. More plain words
    # after any of them make task text, as in `start start caching the list`.
    first_word = words[0]
    if first_word in ("status", "abort"):
        return len(words) == 1
    if first_word == "start":
        return len(words) == 1 or words[1].startswith(("-", "+"))

    return first_word in VERB_WORDS_REPLACED_BY_RESUME + VERB_WORDS_THAT_CARRY_INPUT


def task_command(task_words, modifier, *flags):
    # The `start` line that runs the words as task text, with the user's +fast or +deep kept.
    quoted_task_text = shlex.quote(" ".join(task_words))
    modifier_words = [modifier] if modifier else []
    return script_command(" ".join(["start", *map(shlex.quote, flags), *modifier_words, "--task", quoted_task_text]))


def verb_as_task_refusal(words, parsed, repo_flags):
    # `start` was given a verb name in place of task text: (reason, commands, notes), or None.
    if parsed.plan_args or not first_word_is_verb(words):
        return None

    resume_command = script_command(RESUME_VERB)
    task_command_text = task_command(parsed.positional_words, parsed.modifier, *repo_flags)
    first_word = words[0]
    verb_reason = f"`{first_word}` is a verb, not task text."
    is_resume_word = first_word in VERB_WORDS_REPLACED_BY_RESUME
    if is_resume_word and len(words) > 1:
        return verb_reason, [resume_command, task_command_text], ()

    command = resume_command if is_resume_word else script_command(shlex.join(words))
    return verb_reason, [command], (f"For task text, use `{task_command_text}`.",)


def plain_task_words(parsed):
    # The words of positional task text that holds no plan, phase or run notes, or [] when there are none.
    words = script_utils.words_of_arguments(parsed.positional_words) if parsed.positional_words else []
    if not words:
        return []

    plan_words, _, phase_id, has_phase_flag = split_plan_words(words, parsed)
    return [] if plan_words or phase_id or has_phase_flag else words


def open_run_refusal(repo_dir, previous, args, parsed, repo_flags):
    # An unfinished run blocks `start` unless --restart: (reason, commands, notes), or None. --task does not pass. A
    # run that stopped on the coder's report does not block the session that got the report.
    if not is_run_open(previous) or parsed.restart or reopens_stopped_run(previous):
        return None

    resume_command = script_command(RESUME_VERB)
    reason = f"a /code run is open here: {phase_label(previous)} at stage {previous['stage']}."
    stale_reason = stale_phase_reason(repo_dir, previous)
    if stale_reason:
        reason += f" The run is stale: {stale_reason}."
    if not args:
        return reason, [resume_command], ()

    started_by = previous.get("sessionId")
    if started_by and session_pin() and started_by != session_pin():
        return reason, [script_command("status")], (
            "The run was started by another session, and `start --restart` would drop it: run that only on the "
            "user's word. To run in another checkout, pass `--repo <path>`.",)

    restart_command = script_command(f"start --restart {shlex.join(args)}")
    plain_text_words = plain_task_words(parsed)
    if plain_text_words:
        restart_command = task_command(plain_text_words, parsed.modifier, *repo_flags, "--restart")
    return reason, [resume_command, restart_command], (
        "`resume` goes on with the open run. `start --restart` drops it and starts over.",)


def plan_inside_task_refusal(words, parsed, repo_flags):
    # Task text that starts with a plan or holds `--phase`: (reason, commands, notes), or None.
    plan_words, text_words, phase_id, has_phase_flag = split_plan_words(words, parsed)
    if not (plan_words or parsed.phase_id or has_phase_flag):
        return None

    start_words = ["start", *repo_flags, *plan_words] + (["--phase", phase_id] if phase_id else []) + (
        [parsed.modifier] if parsed.modifier else [])
    commands = [script_command(shlex.join(start_words))]
    # A word that is no plan file (a directory, a ticket id, a source file) may be the first word of the task, so
    # the task choice keeps it in the text.
    has_word_that_is_no_plan_file = any(
        not (os.path.isfile(plan_word) and plan_word.endswith(".md")) for plan_word in plan_words)
    task_words = [*plan_words, *text_words] if has_word_that_is_no_plan_file else text_words
    if task_words:
        commands.append(task_command(task_words, parsed.modifier, *repo_flags))
    return ("the text after the plan or phase is not task text.", commands,
            ("The text after it was not passed to the coder. Tell the user.",))


def task_over_open_phases_refusal(repo_dir, previous, branch, parsed, repo_flags):
    saved_plan = reusable_plan(previous, branch)
    open_phases = open_phase_numbers(repo_dir, saved_plan)
    if not open_phases:
        return None

    resume_command = script_command(RESUME_VERB)
    task_command_text = task_command(parsed.positional_words, parsed.modifier, *repo_flags)
    return (f"{saved_plan} has open phases ({', '.join(open_phases)}).", [resume_command, task_command_text], (
        "`resume` goes on with the plan. `start --task` is for separate work.",))


def start_refusal(repo_dir, previous, branch, args, parsed, repo_flags):
    # Why `start` does not run, as (reason, commands, notes), or None. Checked before anything is written: a verb
    # name as task text, an unfinished run, a plan or --phase inside task text, and task text over a plan with open
    # phases.
    words = script_utils.words_of_arguments(parsed.positional_words) if parsed.positional_words else []
    refusal = verb_as_task_refusal(words, parsed, repo_flags) if words else None
    if refusal:
        return refusal

    refusal = open_run_refusal(repo_dir, previous, args, parsed, repo_flags)
    if refusal:
        return refusal

    refusal = outside_repo_plan_refusal(repo_dir, parsed, repo_flags)
    if refusal or not words:
        return refusal

    refusal = plan_inside_task_refusal(words, parsed, repo_flags)
    if refusal:
        return refusal
    return task_over_open_phases_refusal(repo_dir, previous, branch, parsed, repo_flags)


def open_phase_numbers(repo_dir, plan_rel):
    # The numbers of the plan's phases that are still open, or [] when the plan is unnamed or cannot be read.
    if not plan_rel:
        return []
    try:
        plan_lines = (repo_dir / plan_rel).read_text().splitlines()
    except OSError:
        return []
    entries = plan_format.parse_plan_with_closing_phases(plan_lines)["entries"]
    return [entry["number"] for entry in plan_format.ordered_pending(entries)]


def resolve_plan(repo_dir, argument=None):
    command = ["bash", str(SCRIPTS_DIR / "tools" / "resolve-task-dir.sh")] + ([argument] if argument else [])
    code, output = run_command(command, repo_dir)
    if code == 0:
        return str(pathlib.PurePath(output) / "spec.md"), "eng-spec"
    if code == 5:
        return output, "eng-spec"
    if code == 3:
        ask_user(repo_dir, "several tasks match. Ask the user which one to implement. Then invoke Skill code with "
                 "the chosen plan path.", output)
    else:
        ask_user(repo_dir, "no task or plan resolves. Ask the user what to implement. Then invoke Skill code with a "
                 "plan path or the task text.")
    return None, None


def reusable_plan(previous, branch):
    # The saved plan serves a bare `start` only on the branch it was saved on, and not after a plan with no phases
    # finished.
    if not previous.get("plan") or previous.get("branch") != branch:
        return None
    if previous.get("stage") == "done" and previous.get("phase") is None:
        return None
    return previous["plan"]


def is_finished_single_phase_plan(repo_dir, previous, branch, resolved_plan):
    # A plan with no phases that finished on this branch is not run again when a bare `start` resolves to the same file.
    if previous.get("stage") != "done" or previous.get("phase") is not None or previous.get("branch") != branch:
        return False
    if not previous.get("plan"):
        return False
    try:
        resolved_rel = str(pathlib.Path(resolved_plan).resolve().relative_to(repo_dir))
    except ValueError:
        return False
    return resolved_rel == previous["plan"]


def without_blank_task_text(args):
    # Blank task text is no task text: `start "  "` and `start --task "  "` act as a bare `start`.
    non_blank_args = [word for word in args if word.strip()]
    if parse_start_args(non_blank_args).task_text == "":
        return non_blank_args[:-1]

    return non_blank_args


def prepare_fresh_start(repo_dir, previous, branch, parsed):
    # What a new run does to the old one before it dispatches: settles the saved criteria copy, clears the old say text,
    # stops on a previous phase whose files are not committed yet, and abandons an open dispatch. False after a stop.
    # The state is saved only when a saved copy was restored or dropped, and then under this session.
    criteria_message = None
    if previous.get("criteriaGuard") is not None:
        criteria_message = settle_criteria_guard(repo_dir, previous, branch)
        previous["sessionId"] = session_pin()
        save_state(repo_dir, previous)

    is_auto_advance_text_pending = previous.get("stage") == "done" and previous.get("autoAdvance")
    is_old_text_stale = previous.get("stage") is not None and not is_auto_advance_text_pending
    if is_old_text_stale or parsed.task_text is not None:
        clear_say(repo_dir)

    if criteria_message:
        say(repo_dir, criteria_message)

    if is_auto_advance_text_pending and uncommitted_files(repo_dir, previous):
        emit("stop", "The previous phase's files are not committed yet, so the next phase would take them as "
             f"its own. Run the commit line, then run `{INSTALLED_COMMAND} {RESUME_VERB}`:",
             previous.get("commitLine", ""))
        return False

    abandon_open_dispatch(repo_dir, previous)
    return True


def restart_text_as_run_notes(repo_dir, previous, branch, parsed):
    # `start --restart <text>` over a saved plan with open phases restarts that plan's phase with the text as run notes.
    # Plain text with no saved plan stays task text.
    is_plain_restart_text = parsed.restart and parsed.positional_words and not parsed.plan_args and not parsed.phase_id
    if not is_plain_restart_text:
        return parsed

    saved_plan = reusable_plan(previous, branch)
    open_phases = open_phase_numbers(repo_dir, saved_plan)
    if not open_phases:
        return parsed

    only_phase = previous.get("onlyPhase")
    restart_phase = only_phase if is_run_open(previous) and only_phase in open_phases else None
    words = script_utils.words_of_arguments(parsed.positional_words)
    return parsed._replace(plan_args=[saved_plan], phase_id=restart_phase, task_text=None,
                           positional_words=None, run_notes=" ".join(words))


def command_start(args):
    args = split_quoted_flags(args)
    args = absolute_path_args(args)
    try:
        named_repo = start_repo_path(args)
    except RepoFlagError as error:
        usage_error(str(error))
    repo_dir = repo_root_or_exit(named_repo)
    os.chdir(repo_dir)
    args = without_blank_task_text(args)
    args = phase_words_as_flag(args)
    previous = load_state(repo_dir) or {}
    branch = branch_label(repo_dir)
    parsed = carry_run_notes(parse_start_args(args), reusable_plan(previous, branch))
    parsed = restart_text_as_run_notes(repo_dir, previous, branch, parsed)

    repo_flags = ["--repo", str(repo_dir)] if named_repo else []
    refusal = start_refusal(repo_dir, previous, branch, args, parsed, repo_flags)
    if refusal:
        reason, commands, notes = refusal
        return refuse(reason, *commands, notes=notes)

    start_command = script_command(shlex.join(["start", *args]))
    if stop_while_plan_edit_coder_is_out(repo_dir, previous, start_command):
        return

    if not prepare_fresh_start(repo_dir, previous, branch, parsed):
        return

    if parsed.restart or reopens_stopped_run(previous):
        drop_open_run(repo_dir, previous)

    if parsed.task_text is not None:
        return start_planless(repo_dir, parsed.modifier, parsed.task_text, branch)
    start_plan_run(repo_dir, previous, branch, parsed, start_command)


def resolve_named_task(repo_dir, plan_arg):
    plan_arg, lane = resolve_plan(repo_dir, plan_arg)
    if plan_arg is None:
        return None
    print(f"Resolved the task input: {plan_arg} (lane {lane}).")
    return plan_arg, lane


def resolve_bare_start(repo_dir, previous, branch):
    plan_arg, lane = resolve_plan(repo_dir)
    if plan_arg is None:
        return None
    if is_finished_single_phase_plan(repo_dir, previous, branch, plan_arg):
        return emit("stop", f"The plan {previous['plan']} is complete. Tell the user the plan is complete. "
                    + FOLLOW_UP_HINT)
    print(f"Resolved the task input: {plan_arg} (lane {lane}).")
    return plan_arg, lane


def resolve_start_plan(repo_dir, previous, branch, plan_args):
    # (plan path, lane) of the plan this `start` runs, or None after the stop or question it printed.
    plan_arg = plan_args[0] if plan_args else None
    lane = previous.get("lane", "code")
    is_unknown_arg = plan_arg is not None and not os.path.isfile(plan_arg)
    if is_unknown_arg and (TICKET_ID.match(plan_arg) or os.path.isdir(plan_arg)):
        return resolve_named_task(repo_dir, plan_arg)
    if plan_arg is None and reusable_plan(previous, branch):
        return previous["plan"], lane
    if plan_arg is None:
        return resolve_bare_start(repo_dir, previous, branch)
    return plan_arg, lane if previous.get("plan") == plan_arg else "code"


def load_start_plan(repo_dir, plan_arg, args):
    # (plan path in the repo, plan lines, parsed plan) of a plan that is fit to start, or None after a stop.
    plan_path = pathlib.Path(plan_arg)
    if not os.path.isfile(plan_arg):
        return ask_user(repo_dir, f"no plan file is at {plan_arg}. Ask the user for the path. Then invoke Skill code "
                        "with that path.")
    try:
        plan_rel = str(plan_path.resolve().relative_to(repo_dir))
    except ValueError:
        return ask_user(repo_dir, f"the plan {plan_arg} is outside the repo {repo_dir}. Ask the user for a plan inside "
                        "the repo. Then invoke Skill code with that path.")

    plan_lines = plan_path.read_text().splitlines()
    plan = plan_format.parse_plan_with_closing_phases(plan_lines)
    if plan["failures"]:
        return emit("stop", plan_format.plan_failure_message(plan, plan_rel))

    start_line = RESUME_LINE.format(noun="section", verb=shlex.join(["start", *args]))
    manual_failure = plan_format.manual_format_failure(plan_lines, plan_rel, start_line)
    if manual_failure:
        return emit("stop", manual_failure)

    verification_failure = verification_format_failure(plan_lines, plan_rel, repo_dir, plan["entries"])
    if verification_failure:
        return emit("stop", verification_failure + " " + start_line)
    return plan_rel, plan_lines, plan


def named_phase_stop(entries, phase_id, plan_rel):
    # The stop text for a `--phase` that cannot run, or None when it can.
    entry = next((e for e in entries if e["number"] == phase_id), None)
    if entry is None:
        listed = ", ".join(e["number"] for e in entries) or "none"
        return f"Phase {phase_id} is not in the Phase Status of {plan_rel}. Listed phases: {listed}. Tell the user."
    if entry["moved"]:
        return plan_format.moved_phase_stop(entry, plan_rel)
    if entry["done"]:
        return (f"Phase {phase_id} is already marked done in {plan_rel}. No coder was dispatched. Tell the user; to "
                "run it again, they uncheck it in Phase Status first.")
    return None


def next_phase_stop(entries, pending):
    # The stop text when no phase can start without a named one, or None. The phase to run comes back with it.
    if entries and not pending:
        moved_text = plan_format.moved_phase_text(entries)
        checked_text = f"checked or moved to another ticket ({moved_text})" if moved_text else "checked"
        return f"Every phase in the plan is {checked_text}. Tell the user the plan is complete. " + FOLLOW_UP_HINT

    gated_ahead, entry = plan_format.gate_blockers(pending)
    if gated_ahead:
        return ("No phase was started, and no coder was dispatched: "
                + plan_format.gate_block_text(gated_ahead, entry) + " Tell the user.")
    return None


def pick_start_phase(plan, plan_rel, phase_id, start_command):
    # {"entry": the Phase Status entry to run, or None for a plan with no phases}, or None after a stop.
    entries = plan["entries"]
    if not entries and plan["sections"]:
        return emit("judgment", "The plan has phases but no '## Phase Status' section. Use `git status` and each "
                    "phase's success criteria to pick the next phase, tell the user to backfill the section, then "
                    f"run `{start_command}` again after adding it.")

    if phase_id is not None:
        stop_text = named_phase_stop(entries, phase_id, plan_rel)
        entry = next((e for e in entries if e["number"] == phase_id), None)
    else:
        pending = plan_format.ordered_pending(entries)
        stop_text = next_phase_stop(entries, pending)
        entry = plan_format.gate_blockers(pending)[1]
    if stop_text:
        return emit("stop", stop_text)
    return {"entry": entry}


def start_plan_run(repo_dir, previous, branch, parsed, start_command):
    resolved = resolve_start_plan(repo_dir, previous, branch, parsed.plan_args)
    if resolved is None:
        return
    plan_arg, lane = resolved

    args_for_resume = shlex.split(start_command)[len(shlex.split(script_command(""))):]
    loaded = load_start_plan(repo_dir, plan_arg, args_for_resume[1:])
    if loaded is None:
        return
    plan_rel, plan_lines, plan = loaded

    picked = pick_start_phase(plan, plan_rel, parsed.phase_id, start_command)
    if picked is None:
        return
    entry = picked["entry"]

    number = entry["number"] if entry else None
    section = plan_format.phase_text(plan_lines, number) if entry else "\n".join(plan_lines)
    closing_skill_name = plan_format.closing_skill(entry["title"]) if entry else None
    if closing_skill_name and parsed.run_notes:
        return emit("stop", f"Phase {number} is a closing phase and takes no run notes: they were not passed on. "
                    "Tell the user.")
    if closing_skill_name:
        return start_closing_phase(repo_dir, plan_rel, lane, parsed, entry, closing_skill_name, section, branch)

    if not check_acceptance_criteria(repo_dir, plan_rel):
        return
    start_phase_coder(repo_dir, previous, branch, parsed, {
        "plan_rel": plan_rel, "lane": lane, "entry": entry, "section": section, "has_phases": bool(plan["sections"])})


def start_phase_coder(repo_dir, previous, branch, parsed, phase):
    plan_rel, entry, section = phase["plan_rel"], phase["entry"], phase["section"]
    number = entry["number"] if entry else None
    use_packet = phase["has_phases"] and entry
    state_phase = number if use_packet else None
    is_same_unfinished_phase = (previous.get("plan") == plan_rel and previous.get("phase") == state_phase
                             and previous.get("stage") not in (None, "done") and previous.get("baseline") is not None)
    baseline = previous["baseline"] if is_same_unfinished_phase else file_hashes(repo_dir)
    base_head = (
        previous.get("baseHead") if is_same_unfinished_phase and previous.get("baseHead") else head_commit(repo_dir)
    )

    commands = derive_gate_commands(repo_dir, section) if entry else []
    if entry:
        stale_prose_script = pathlib.Path(__file__).resolve().parent / "stale_prose.py"
        commands.append(f"python3 {stale_prose_script} --base {base_head}")
    gate_note = set_gate_and_packet_note(repo_dir, plan_rel, commands)
    packet_body = packet_text(repo_dir, plan_rel, number, use_packet)
    run_id = start_run(repo_dir)

    phase_description = f"Phase {number} of `{plan_rel}`" if use_packet else f"`{plan_rel}`"
    prompt = (f"Implement {phase_description}. Read the plan phase-scoped.\n"
              f"{ENG_SPEC_BRIEF}\n\n" + packet_body).rstrip()
    prompt = "\n".join([prompt, *run_notes_lines(parsed.run_notes)])
    state = {"stage": "coder", "plan": plan_rel, "lane": phase["lane"], "phase": state_phase, "branch": branch,
             "modifier": parsed.modifier, "risk": entry["risk"] if entry else "high",
             "title": entry["title"] if entry else "", "gateCommands": commands, "baseline": baseline,
             "baseHead": base_head, "startedAt": time.time(), "phaseText": section if use_packet else None,
             "onlyPhase": parsed.phase_id, "headless": parsed.headless, "sessionId": session_pin(), "runId": run_id}
    open_dispatch(state)
    save_state(repo_dir, state)
    model = "haiku" if parsed.modifier == "+fast" else None
    emit_dispatch(repo_dir, state, RESUME_VERB, gate_note, prompt=prompt, agent="coder", model=model)


def start_planless(repo_dir, modifier, task_text, branch="-"):
    # A new task has no earlier rulings: the ones of a previous planless task do not carry over.
    ruled_asks_path(repo_dir).unlink(missing_ok=True)
    state = {"stage": "coder", "plan": None, "lane": "code", "phase": None, "branch": branch, "modifier": modifier,
             "risk": "high", "title": "", "gateCommands": [], "baseline": file_hashes(repo_dir),
             "startedAt": time.time(), "sessionId": session_pin(), "runId": start_run(repo_dir)}
    open_dispatch(state)
    save_state(repo_dir, state)
    prompt = (f"Implement: {task_text}\nRun the typecheck, and lint and tests for only the files you changed, once, "
              f"after all edits. {ENG_SPEC_BRIEF}")
    model = "haiku" if modifier == "+fast" else None
    emit_dispatch(repo_dir, state, RESUME_VERB, prompt=prompt, agent="coder", model=model)


def start_closing_phase(repo_dir, plan_rel, lane, parsed, entry, skill, section, branch):
    state = {"stage": "skill", "plan": plan_rel, "lane": lane, "phase": entry["number"], "branch": branch,
             "modifier": parsed.modifier, "risk": entry["risk"], "title": entry["title"], "gateCommands": [],
             "behavior": [], "baseline": file_hashes(repo_dir), "onlyPhase": parsed.phase_id,
             "headless": parsed.headless, "sessionId": session_pin()}
    save_state(repo_dir, state)
    emit_closing_skill(repo_dir, plan_rel, entry["number"], entry["title"], skill, section)


def emit_closing_skill(repo_dir, plan_rel, number, title, skill, section):
    open_items = plan_format.open_success_items(section.split("\n")) if section else []
    is_refactor = skill == REFACTOR_SKILL
    gate = concentration_gate(repo_dir) if is_refactor else None
    pass_command = evidence_command_shape(len(open_items)) + simplify_option(gate)
    verdict_step = (f"run `{pass_command}` when the phase's Success "
                   "Criteria hold, or `skill-done fail --finding \"<one line>\"` (one `--finding` per open finding) "
                   "when they do not (for the Verify pass, any MISSING criterion fails it)")
    section_lines = (
        ["The phase's own plan section follows. Follow its steps and gates; the skill alone is not the phase:", section]
        if section
        else []
    )
    gate_report = gate_lines(gate) if is_refactor else []
    ruled_asks = ruled_asks_lines(repo_dir, plan_rel)
    ruled_lines = (
        ["Asks already ruled in this run. Never raise one of them again, and never undo its outcome:",
         *[f"- {ruled_ask}" for ruled_ask in ruled_asks]]
        if ruled_asks
        else []
    )
    emit(
        "invoke-skill",
        f"Phase {number} ({title}) is a closing phase. Invoke the Skill tool with "
        f"`{skill}`; a coder is not dispatched.",
        *section_lines,
        *ruled_lines,
        *gate_report,
        *evidence_request_lines(open_items),
        f"The skill needs judgment. When it returns, {verdict_step}.",
    )


def check_acceptance_criteria(repo_dir, plan_rel):
    if plan_format.missing_criteria_failure(repo_dir / plan_rel) is None:
        return True

    criteria_path = criteria_rel(plan_rel)

    note = f"{criteria_path} is missing or empty"
    run_command(["bash", str(SCRIPTS_DIR / "telemetry" / "log-scan"), f"repo={repo_dir.name}", "scan=acceptance-stub",
                 "stage=code-phase", "exit=0", "candidates=1", "confirmed=1", f"note={note}"], repo_dir)
    emit("stop", f"Plan defect: {note}, and the plan has an Acceptance Criteria section.",
         "Do not dispatch. Do not write the criteria. Report the defect to the user and wait.")
    return False


def set_gate_and_packet_note(repo_dir, plan_rel, commands):
    if not commands:
        return "GATE: none derived; the coder runs its own checks (the packet says so)."

    # The gate runs the commands later, at each hand-back, so the repo's gate env goes into the stored gate.
    gate_env = plan_format.repo_gate_env(repo_dir, plan_rel)
    env_arguments = [argument for assignment in gate_env for argument in ("--env", assignment)]
    gate_script = str(SCRIPTS_DIR / "code" / "coder_gate.py")
    code, output = run_command(["python3", gate_script, "set", *env_arguments, *commands], repo_dir)
    if code != 0:
        return f"GATE: not set ({output.splitlines()[0] if output else 'refused'}); the coder runs its own checks."

    env_note = f" With: {' '.join(gate_env)}." if gate_env else ""
    return f"GATE: {output}. Commands: " + " | ".join(commands) + env_note


def packet_text(repo_dir, plan_rel, number, use_packet):
    if not use_packet:
        return ""
    packet_script = str(SCRIPTS_DIR / "code" / "coder_packet.py")
    code, output = run_command(["python3", packet_script, plan_rel, str(number)], repo_dir)
    if code != 0:
        sys.exit(f"code-step: coder-packet failed: {output}")
    return output
