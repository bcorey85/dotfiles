#!/usr/bin/env python3
"""code_step.py: the routing of /code as a script. The forked Sonnet subagent of /code runs one verb, reads its
ACTION lines, does exactly that, and runs the next verb. The script builds every prompt and every argument.

  code_step.py start [<plan>] [+fast|+deep] [--phase <id>] [--restart]
                                                next phase of the plan (or the named one): checks, gate, packet, the
                                                exact coder dispatch. `start --help` prints usage. --restart drops an
                                                unfinished run first.
  code_step.py start --task "<text>"           planless work: the coder dispatch without gate or packet
  code_step.py resume                           do the next step of the saved run, whatever stage or stop it is in
  code_step.py decide <adopt|keep> --by <user|session> --ruling "<the decision in one line>"
                                                only --by user is the user's own word: a session ruling never changes
                                                a criterion
  code_step.py decide discuss                   ask the user how to rule when the code and the plan disagree; records
                                                nothing
  code_step.py asks-done <outcome>...           log the user's answer to each ask[] entry, then run the phase gates
  code_step.py skill-done <pass|fail>          a closing phase's skill returned: mark it done (pass) or stop (fail)
  code_step.py verify                           re-run the phase gates after a failed Automated Verification was fixed
  code_step.py review-again                     dispatch the review loop again on the same diff, after its packet did
                                                not parse
  code_step.py tick <phase id>                  mark a phase done that the user finished outside /code
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
Run from the repo root. State lives in <git dir>/code-step/. Env CODE_STEP_CLAUDE_DIR overrides the toolkit folder;
CODE_STEP_NVIM_JUMP overrides the nvim-jump command.
Each run also keeps <git dir>/code-step/runs/<run id>/events.jsonl and one prompt-<dispatch id>.txt per dispatch. The
hooks write only that log; the verbs read it and write state.json.

The code is split in four files that import one way: code_step_core (state, event log, hand-back matcher, output),
code_step_boundary (criteria guard, verification runner, phase boundary), code_step_hooks, and this file."""
import collections
import json
import os
import pathlib
import re
import shlex
import shutil
import sys
import time

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import plan_format
import script_utils
from code_step_boundary import (
    command_skill_done,
    command_tick,
    command_verify,
    criteria_file,
    criteria_rel,
    finish_phase,
    mark_review_gate_clean,
    save_criteria_guard,
    settle_criteria_guard,
    stop_while_plan_edit_coder_is_out,
    verification_format_failure,
)
from code_step_core import (
    CLAUDE_DIR,
    CODER,
    CODER_STAGES,
    HOOK_STAGES,
    INSTALLED_COMMAND,
    RESUME_LINE,
    RESUME_VERB,
    REVIEW_LOOP,
    SCRIPTS_DIR,
    StateFileError,
    abandon_open_dispatch,
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
    emit_dispatch,
    file_hashes,
    head_commit,
    load_handback,
    load_state,
    open_dispatch,
    phase_coder_reports,
    pin_session,
    put_resumed_coder_back,
    put_resumed_review_back,
    refuse,
    repo_root_or_exit,
    restart_instruction,
    resumed_agent_pending_stop,
    save_state,
    say,
    script_command,
    sent_message_since,
    session_pin,
    start_run,
    state_dir,
    timed_command,
    uncommitted_files,
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
from script_utils import git_output, run_command

PLAN_IMPACT_OPTIONS = ["Adopt plan change", "Keep plan as written", "Discuss"]
DECISION_WORDS = {"adopt": PLAN_IMPACT_OPTIONS[0], "keep": PLAN_IMPACT_OPTIONS[1], "discuss": PLAN_IMPACT_OPTIONS[2]}
START_USAGE = ('usage: code_step.py start [<plan>] [+fast|+deep] [--phase <id>] [--restart]\n'
               '       code_step.py start --task "<task text>"\n'
               '--phase <id> starts the named phase. Text that follows the plan (or comes first, when there is no '
               'plan file, ticket id or directory) is the task text. A flag before it, or after a plan, must be '
               'known. --restart drops an unfinished run and starts over.')
START_MODIFIERS = ("+fast", "+deep")
FOLLOW_UP_HINT = ("A follow-up change to a finished plan needs the task text: invoke Skill code with "
                  "`start --task \"<text>\"`.")
WAITING_STAGES = ("asks", "impact-coder", "impact-review", "skill", "plan-coder")
ASKS_DONE_USAGE = ("asks-done needs one outcome per ask: accepted, rejected or modified. Each modified ask needs the "
                   "user's change after it as `--change \"<text>\"`.")
# The state each guarded verb needs: the stages it may run at, the stop reasons it accepts when the stage is "stopped",
# and the refusal text when the state is anything else. `start`, `tick` and `resume` run at any stage and are not in
# the table. A review-loop resumed after the wait cap also counts for review-again.
STAGE_GUARDS = {
    "decide": {"stages": ("impact-coder", "impact-review"),
               "message": "decide needs a pending PLAN-IMPACT and one word: adopt, keep or discuss."},
    "review-again": {"stages": ("stopped",), "stopReasons": ("invalid-packet",),
                     "message": "review-again ran with no unreadable review packet or silent review-loop pending."},
    "asks-done": {"stages": ("asks",), "message": ASKS_DONE_USAGE},
    "skill-done": {"stages": ("skill",), "message": "skill-done ran with no closing-phase skill pending."},
    "verify": {"stages": ("stopped",), "stopReasons": ("verification", "plan-format"),
               "message": "verify ran with no failed Automated Verification or unparsed Manual Verification pending."},
}
# The verbs that older printed commands still name. Each one now does what `resume` does.
RESUME_ALIASES = ("after-coder", "after-review", "after-plan-edit")
VERB_WORDS_REPLACED_BY_RESUME = ("continue", "resume", *RESUME_ALIASES)
VERB_WORDS_THAT_CARRY_INPUT = ("review-again", "decide", "asks-done", "skill-done", "tick", "verify")
# These verbs open a new /code run after the user answered. The last run's say.md text was already handed back.
VERBS_THAT_CLEAR_SAY = ("decide", "asks-done", "verify", "review-again")
# The saved stage of a run and the step that comes next for it. `stopped` and an unknown stage are routed by code.
STAGE_ROUTES = {
    "coder": "after-coder", "asks-coder": "after-coder", "review": "after-review", "plan-coder": "after-plan-edit",
    "impact-coder": "ask-impact", "impact-review": "ask-impact", "asks": "ask-asks", "done": "done",
}
NO_CODER_REPORT = ("No coder report was saved. The log-hook (code_step.py log-hook) is not installed or the coder "
                   "never handed back. Tell the user.")
NO_REVIEW_PACKET = ("No review-loop packet was saved. The log-hook (code_step.py log-hook) is not installed. "
                    "Tell the user.")
TICKET_ID = re.compile(r"^[A-Za-z]+-\d+$")
CARGO_CLIPPY = "cargo clippy --all-targets -- -D warnings"
TYPECHECK_SCRIPTS = ["typecheck", "type-check", "check-types", "tsc"]
SCRIPT_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mts", ".mjs")
TEST_SUFFIXES = ".test.ts,.test.tsx,.spec.ts,.spec.tsx,.test.js,.test.jsx"
TEST_FILE = re.compile(r"\.(test|spec)\.|(^|/)test_[^/]*\.py$|_test\.py$")
BARE_CARGO_MANIFEST = re.compile(r"`(Cargo\.toml)`")
PATH_IN_BACKTICKS = re.compile(r"`([\w.@-]+(?:/[\w.@\[\]()-]+)+\.\w+)(?::\d+(?:-\d+)?)?`")


# ---------- plan check ----------

def command_plan(args):
    if len(args) < 2 or args[0] not in ("check", "parse"):
        sys.exit("usage: code_step.py plan check|parse <path>")
    plan_lines = pathlib.Path(args[1]).read_text().splitlines()
    plan = plan_format.parse_plan_with_closing_phases(plan_lines)
    if args[0] == "parse":
        return print(json.dumps(plan, indent=1))
    for row in plan_format.plan_failure_rows(plan, args[1]):
        print(row)
    manual_failure = plan_format.manual_format_failure(plan_lines, args[1])
    if manual_failure:
        print(manual_failure)
    verification_failure = verification_format_failure(plan_lines, args[1], pathlib.Path.cwd(), plan["entries"])
    if verification_failure:
        print(verification_failure)
    sys.exit(1 if plan["failures"] or manual_failure or verification_failure else 0)


# ---------- gate derivation ----------

def nearest_directory_with(repo_dir, rel_path, manifest_name):
    manifest = script_utils.nearest_file_upward((repo_dir / rel_path).parent, manifest_name, repo_dir)
    return manifest.parent if manifest else None


def in_directory(command, package_rel):
    return f"cd {shlex.quote(package_rel)} && {command}" if package_rel else command


def script_package_commands(repo_dir, package_dir, paths):
    package_json = json.loads((package_dir / "package.json").read_text())
    scripts = package_json.get("scripts", {})
    dependencies = {**package_json.get("dependencies", {}), **package_json.get("devDependencies", {})}
    package_rel = script_utils.directory_relative_to(repo_dir, package_dir)
    relative_paths = [str((repo_dir / path).relative_to(package_dir)) for path in paths]
    commands = []

    typecheck_name = next((name for name in TYPECHECK_SCRIPTS if name in scripts), None)
    if typecheck_name:
        commands.append(in_directory(f"npm run {typecheck_name}", package_rel))
    elif (package_dir / "tsconfig.json").is_file():
        commands.append(in_directory("npx tsc --noEmit", package_rel))

    source_suffixes = sorted({pathlib.Path(p).suffix for p in relative_paths
                             if p.endswith(SCRIPT_SUFFIXES) and not TEST_FILE.search(p)}
                            | {pathlib.Path(p).suffix for p in relative_paths if p.endswith(SCRIPT_SUFFIXES)})
    if ("eslint" in dependencies or "lint" in scripts) and source_suffixes:
        commands.append(in_directory("npx eslint {files:" + ",".join(source_suffixes) + "}", package_rel))

    test_paths = [p for p in relative_paths if TEST_FILE.search(p)]
    runner = "vitest run" if "vitest" in dependencies else "jest" if "jest" in dependencies else None
    if runner:
        scope = " ".join(shlex.quote(p) for p in test_paths) or "{files:" + TEST_SUFFIXES + "}"
        commands.append(in_directory(f"npx {runner} {scope}", package_rel))
    elif "test" in scripts:
        scope = " ".join(shlex.quote(p) for p in test_paths) or "{files:" + TEST_SUFFIXES + "}"
        commands.append(in_directory(f"npm test -- {scope}", package_rel))
    return commands


def python_commands(repo_dir, paths):
    python_paths = [p for p in paths if p.endswith(".py")]
    if not python_paths or not any(
        (repo_dir / name).is_file() for name in ("pyproject.toml", "pytest.ini", "setup.cfg")
    ):
        return []
    commands = []
    pyproject = (repo_dir / "pyproject.toml")
    if pyproject.is_file() and "ruff" in pyproject.read_text():
        commands.append("ruff check {files:.py}")
    test_paths = [p for p in python_paths if TEST_FILE.search(p)]
    scope = " ".join(shlex.quote(p) for p in test_paths) or "{files:_test.py}"
    commands.append(f"python3 -m pytest {scope}")
    return commands


def cargo_test_scope(crate_dir, file_in_crate):
    # The cargo test arguments for one Rust file, given the crate directory and the file's path from it, or None when
    # no test belongs to it. `src/bin/<name>.rs` and every file under `src/bin/<name>/` are the binary `<name>`.
    # Any other file under `src/`, `lib.rs` and `main.rs` included, runs the library and binary unit tests
    # (`--lib --bins`) in a crate with a `src/lib.rs`, and the binaries (`--bins`) in a crate with none; `--lib` alone
    # would skip the unit tests in `main.rs` and in the modules only `main.rs` reaches. `tests/<name>.rs` is the test
    # target `<name>`. Any file under `tests/<dir>/` is the test target `<dir>` when `tests/<dir>/main.rs` exists, and
    # otherwise a helper that any integration test can include, so it runs every test target (`--tests`),
    # which already covers the library and every binary, so the crate's other test commands are dropped.
    # A `src/` change does not run the integration tests in `tests/`, because CI runs the full suite.
    # No module filter: a test in an unchanged module can pin the old behavior of the changed one, and the cost is
    # compiling the test binary, which a filter does not save.
    parts = pathlib.PurePosixPath(file_in_crate).with_suffix("").parts
    if len(parts) < 2:
        return None

    if parts[0] == "tests":
        if len(parts) == 2:
            return f"--test {parts[1]}"

        is_target_main_file = parts[2:] == ("main",)
        is_test_target_directory = is_target_main_file or (crate_dir / "tests" / parts[1] / "main.rs").is_file()
        return f"--test {parts[1]}" if is_test_target_directory else "--tests"

    if parts[0] != "src":
        return None

    is_under_bin_directory = parts[1] == "bin" and len(parts) > 2
    if is_under_bin_directory:
        return f"--bin {parts[2]}"

    if (crate_dir / "src" / "lib.rs").is_file():
        return "--lib --bins"
    return "--bins"


def cargo_commands(repo_dir, paths):
    commands_by_crate = {}
    for path in paths:
        is_rust_file = path.endswith(".rs")
        if not (is_rust_file or pathlib.PurePosixPath(path).name == "Cargo.toml"):
            continue

        crate_dir = nearest_directory_with(repo_dir, path, "Cargo.toml")
        if crate_dir is None:
            continue

        crate_commands = commands_by_crate.setdefault(crate_dir, [CARGO_CLIPPY])
        if not is_rust_file:
            continue

        path_in_crate = str((repo_dir / path).relative_to(crate_dir))
        scope = cargo_test_scope(crate_dir, path_in_crate)
        test_command = f"cargo test {scope}" if scope else None
        if test_command and test_command not in crate_commands:
            crate_commands.append(test_command)

    commands = []
    for crate_dir, crate_commands in commands_by_crate.items():
        if "cargo test --tests" in crate_commands:
            crate_commands = [CARGO_CLIPPY, "cargo test --tests"]

        crate_rel = script_utils.directory_relative_to(repo_dir, crate_dir)
        commands += [in_directory(command, crate_rel) for command in crate_commands]
    return commands


def derive_gate_commands(repo_dir, phase_section):
    paths = []
    for match in PATH_IN_BACKTICKS.finditer(phase_section):
        if match.group(1) not in paths:
            paths.append(match.group(1))

    by_package = {}
    for path in paths:
        package_dir = nearest_directory_with(repo_dir, path, "package.json")
        if package_dir is not None:
            by_package.setdefault(package_dir, []).append(path)

    commands = []
    for package_dir, package_paths in by_package.items():
        commands += script_package_commands(repo_dir, package_dir, package_paths)
    root_manifests = BARE_CARGO_MANIFEST.findall(phase_section)
    commands += cargo_commands(repo_dir, paths + root_manifests)
    commands += python_commands(repo_dir, paths)
    return commands


# ---------- start ----------

def usage_error(message):
    print(f"code_step.py start: {message}\n{START_USAGE}", file=sys.stderr)
    sys.exit(2)


StartArgs = collections.namedtuple("StartArgs", "modifier plan_args task_text phase_id restart positional_words")


def looks_like_plan_argument(word):
    path = pathlib.Path(word)
    # A word with whitespace is task text that happens to name a file, unless it is itself a file (a real plan whose
    # path has a space).
    if script_utils.has_whitespace(word) and not path.is_file():
        return False

    return looks_like_plan_path(word) or TICKET_ID.match(word) is not None or path.is_file() or path.is_dir()


def looks_like_plan_path(argument):
    return "/" in argument or argument.endswith(".md")


def is_flag(word):
    return word.startswith("-") and len(word) > 1


def starts_task_text(word):
    return word not in START_MODIFIERS and not is_flag(word) and not looks_like_plan_argument(word)


def phase_flag_value(args, position):
    # The id after `--phase`; a missing id, or a flag in its place, exits 2.
    if position + 1 >= len(args) or args[position + 1].startswith("-"):
        usage_error("--phase needs a phase id")
    return args[position + 1]


def reject_unknown_flag(word):
    # --restart is the one flag besides --phase and --task. --help prints usage and exits 0 before any state is
    # touched; any other flag exits 2.
    if word in ("--help", "-h"):
        print(START_USAGE)
        sys.exit(0)
    if word != "--restart":
        usage_error(f"unknown flag {word}")


def parse_start_args(args):
    # Flags are read left to right up to the first word that is not a plan file, ticket id or directory: that word
    # and everything after it is task text, as is everything after --task. positional_words holds the words of task
    # text that did not follow --task (None otherwise): start_refusal reads them.
    modifiers = []
    plan_args = []
    task_text = None
    positional_words = None
    phase_id = None
    restart = False
    position = 0
    while position < len(args):
        word = args[position]
        if word == "--task":
            task_text = " ".join(args[position + 1:])
            break
        if word == "--phase":
            phase_id = phase_flag_value(args, position)
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
            restart = True
        else:
            plan_args.append(word)
        position += 1
    modifier = "+deep" if "+deep" in modifiers else "+fast" if modifiers else None
    return StartArgs(modifier, plan_args, task_text, phase_id, restart, positional_words)


def phase_label(state):
    plan_name = state.get("plan") or "a task with no plan"
    return f"Phase {state['phase']} of {plan_name}" if state.get("phase") is not None else plan_name


def phase_flag_position(words):
    # Where an explicit `--phase <phase id>` sits in the words, or None. A `--phase` with no word after it, or with a
    # word that is not a phase id after it, is part of the text.
    for index, word in enumerate(words):
        is_last = index + 1 >= len(words)
        if word == "--phase" and not is_last and re.fullmatch(plan_format.PHASE_ID, words[index + 1]):
            return index

    return None


def first_word_is_verb(words):
    # Whether `start` was given a verb name in place of task text. `start` and `status` are verbs only where a verb
    # would fit: `status` alone, and `start` alone or before a flag or a modifier. More plain words after either make
    # task text, as in `start start caching the list`.
    first_word = words[0]
    if first_word == "status":
        return len(words) == 1
    if first_word == "start":
        return len(words) == 1 or words[1].startswith(("-", "+"))

    return first_word in VERB_WORDS_REPLACED_BY_RESUME + VERB_WORDS_THAT_CARRY_INPUT


def task_command(task_words, modifier):
    # The `start` line that runs the words as task text, with the user's +fast or +deep kept.
    quoted_task_text = shlex.quote(" ".join(task_words))
    modifier_words = [modifier] if modifier else []
    return script_command(" ".join(["start", *modifier_words, "--task", quoted_task_text]))


def verb_as_task_refusal(words, parsed):
    # `start` was given a verb name in place of task text: (reason, commands, notes), or None.
    if parsed.plan_args or not first_word_is_verb(words):
        return None

    resume_command = script_command(RESUME_VERB)
    task_command_text = task_command(parsed.positional_words, parsed.modifier)
    first_word = words[0]
    verb_reason = f"`{first_word}` is a verb, not task text."
    is_resume_word = first_word in VERB_WORDS_REPLACED_BY_RESUME
    if is_resume_word and len(words) > 1:
        return verb_reason, [resume_command, task_command_text], ()

    command = resume_command if is_resume_word else script_command(shlex.join(words))
    return verb_reason, [command], (f"For task text, use `{task_command_text}`.",)


def open_run_refusal(previous, args, parsed):
    # An unfinished run blocks `start` unless --restart: (reason, commands, notes), or None. --task does not pass.
    if previous.get("stage") in (None, "done") or parsed.restart:
        return None

    resume_command = script_command(RESUME_VERB)
    reason = f"a /code run is open here: {phase_label(previous)} at stage {previous['stage']}."
    if not args:
        return reason, [resume_command], ()

    restart_command = script_command(f"start --restart {shlex.join(args)}")
    return reason, [resume_command, restart_command], (
        "`resume` goes on with the open run. `start --restart` drops it and starts over.",)


def split_plan_words(words, parsed):
    # (plan words, task words, phase id, whether the text held a `--phase <id>`) for task text that may hold a plan.
    # Only a plan file as the first word, a plan argument before the text, or an explicit --phase is not task text.
    plan_words = list(parsed.plan_args)
    is_plan_file_first = not plan_words and pathlib.Path(words[0]).is_file()
    if is_plan_file_first:
        plan_words = [words[0]]
    text_words = words[1:] if is_plan_file_first else list(words)
    phase_id = parsed.phase_id
    phase_flag_at = phase_flag_position(text_words)
    if phase_flag_at is not None:
        phase_id = text_words[phase_flag_at + 1]
        del text_words[phase_flag_at:phase_flag_at + 2]
    return plan_words, text_words, phase_id, phase_flag_at is not None


def plan_inside_task_refusal(words, parsed):
    # Task text that starts with a plan or holds `--phase`: (reason, commands, notes), or None.
    plan_words, text_words, phase_id, has_phase_flag = split_plan_words(words, parsed)
    if not (plan_words or parsed.phase_id or has_phase_flag):
        return None

    start_words = ["start", *plan_words] + (["--phase", phase_id] if phase_id else []) + (
        [parsed.modifier] if parsed.modifier else [])
    commands = [script_command(shlex.join(start_words))]
    # A word that is no plan file (a directory, a ticket id, a source file) may be the first word of the task, so
    # the task choice keeps it in the text.
    has_word_that_is_no_plan_file = any(
        not (pathlib.Path(plan_word).is_file() and plan_word.endswith(".md")) for plan_word in plan_words)
    task_words = [*plan_words, *text_words] if has_word_that_is_no_plan_file else text_words
    if task_words:
        commands.append(task_command(task_words, parsed.modifier))
    return ("the text after the plan or phase is not task text.", commands,
            ("The text after it was not passed to the coder. Tell the user.",))


def task_over_open_phases_refusal(repo_dir, previous, branch, parsed):
    saved_plan = reusable_plan(previous, branch)
    open_phases = open_phase_numbers(repo_dir, saved_plan)
    if not open_phases:
        return None

    resume_command = script_command(RESUME_VERB)
    task_command_text = task_command(parsed.positional_words, parsed.modifier)
    return (f"{saved_plan} has open phases ({', '.join(open_phases)}).", [resume_command, task_command_text], (
        "`resume` goes on with the plan. `start --task` is for separate work.",))


def start_refusal(repo_dir, previous, branch, args, parsed):
    # Why `start` does not run, as (reason, commands, notes), or None. Checked before anything is written: a verb
    # name as task text, an unfinished run, a plan or --phase inside task text, and task text over a plan with open
    # phases.
    words = script_utils.words_of_arguments(parsed.positional_words) if parsed.positional_words else []
    refusal = verb_as_task_refusal(words, parsed) if words else None
    if refusal:
        return refusal

    refusal = open_run_refusal(previous, args, parsed)
    if refusal or not words:
        return refusal

    refusal = plan_inside_task_refusal(words, parsed)
    if refusal:
        return refusal
    return task_over_open_phases_refusal(repo_dir, previous, branch, parsed)


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


def command_start(args):
    args = without_blank_task_text(args)
    parsed = parse_start_args(args)
    repo_dir = repo_root_or_exit()
    os.chdir(repo_dir)
    previous = load_state(repo_dir) or {}
    branch = branch_label(repo_dir)

    refusal = start_refusal(repo_dir, previous, branch, args, parsed)
    if refusal:
        reason, commands, notes = refusal
        return refuse(reason, *commands, notes=notes)

    start_command = script_command(shlex.join(["start", *args]))
    if stop_while_plan_edit_coder_is_out(repo_dir, previous, start_command):
        return

    if not prepare_fresh_start(repo_dir, previous, branch, parsed):
        return

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
    is_unknown_arg = plan_arg is not None and not pathlib.Path(plan_arg).is_file()
    if is_unknown_arg and (TICKET_ID.match(plan_arg) or pathlib.Path(plan_arg).is_dir()):
        return resolve_named_task(repo_dir, plan_arg)
    if plan_arg is None and reusable_plan(previous, branch):
        return previous["plan"], lane
    if plan_arg is None:
        return resolve_bare_start(repo_dir, previous, branch)
    return plan_arg, lane if previous.get("plan") == plan_arg else "code"


def load_start_plan(repo_dir, plan_arg, args):
    # (plan path in the repo, plan lines, parsed plan) of a plan that is fit to start, or None after a stop.
    plan_path = pathlib.Path(plan_arg)
    if not plan_path.is_file():
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
    if closing_skill_name:
        return start_closing_phase(repo_dir, plan_rel, lane, parsed.modifier, entry, closing_skill_name, section,
                                   branch, parsed.phase_id)

    if not check_acceptance_criteria(repo_dir, plan_lines, plan_rel):
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
              "If the task turns out architectural, report back and recommend /eng-spec.\n\n" + packet_body).rstrip()
    state = {"stage": "coder", "plan": plan_rel, "lane": phase["lane"], "phase": state_phase, "branch": branch,
             "modifier": parsed.modifier, "risk": entry["risk"] if entry else "high",
             "title": entry["title"] if entry else "", "gateCommands": commands, "baseline": baseline,
             "baseHead": base_head, "startedAt": time.time(), "phaseText": section if use_packet else None,
             "onlyPhase": parsed.phase_id, "sessionId": session_pin(), "runId": run_id}
    open_dispatch(state)
    save_state(repo_dir, state)
    model = "haiku" if parsed.modifier == "+fast" else None
    emit_dispatch(repo_dir, state, RESUME_VERB, gate_note, prompt=prompt, agent="coder", model=model)


def start_planless(repo_dir, modifier, task_text, branch="-"):
    state = {"stage": "coder", "plan": None, "lane": "code", "phase": None, "branch": branch, "modifier": modifier,
             "risk": "high", "title": "", "gateCommands": [], "baseline": file_hashes(repo_dir),
             "startedAt": time.time(), "sessionId": session_pin(), "runId": start_run(repo_dir)}
    open_dispatch(state)
    save_state(repo_dir, state)
    prompt = (f"Implement: {task_text}\nRun the typecheck, and lint and tests for only the files you changed, once, "
              "after all edits. If the task turns out architectural, report back and recommend /eng-spec.")
    model = "haiku" if modifier == "+fast" else None
    emit_dispatch(repo_dir, state, RESUME_VERB, prompt=prompt, agent="coder", model=model)


def start_closing_phase(repo_dir, plan_rel, lane, modifier, entry, skill, section, branch, only_phase=None):
    state = {"stage": "skill", "plan": plan_rel, "lane": lane, "phase": entry["number"], "branch": branch,
             "modifier": modifier, "risk": entry["risk"], "title": entry["title"], "gateCommands": [], "behavior": [],
             "baseline": file_hashes(repo_dir), "onlyPhase": only_phase, "sessionId": session_pin()}
    save_state(repo_dir, state)
    emit_closing_skill(entry["number"], entry["title"], skill, section)


def emit_closing_skill(number, title, skill, section):
    verdict_step = ("run `python3 ~/.claude/scripts/code/code_step.py skill-done pass` when the phase's Success "
                   "Criteria hold, or `skill-done fail` when they do not (for the Verify pass, any MISSING "
                   "criterion fails it)")
    section_lines = (
        ["The phase's own plan section follows. Follow its steps and gates; the skill alone is not the phase:", section]
        if section
        else []
    )
    emit(
        "invoke-skill",
        f"Phase {number} ({title}) is a closing phase. Invoke the Skill tool with "
        f"`{skill}`; a coder is not dispatched.",
        *section_lines,
        f"The skill needs judgment. When it returns, {verdict_step}.",
    )


def check_acceptance_criteria(repo_dir, plan_lines, plan_rel):
    has_criteria_section = any(plan_format.ACCEPTANCE_HEADING.match(line) for line in plan_lines)
    if not has_criteria_section:
        return True
    criteria_path = criteria_rel(plan_rel)
    criteria = repo_dir / criteria_path
    if criteria.is_file() and criteria.read_text().strip():
        return True

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


# ---------- coder hand-back ----------

def take_handback(repo_dir, state, agent_type, missing_text):
    # The hand-back event of the agent the verb waited for, after a resumed agent is put back in its stage; None after
    # printing the stop. A resumed agent that has not handed back yet gets its own stop.
    is_resumed = awaits_resumed_coder(state) or awaits_resumed_review(state)
    handback = awaited_handback(repo_dir, state)
    if handback is None:
        return emit("stop", resumed_agent_pending_stop(agent_type) if is_resumed else missing_text)

    pin_session(repo_dir, state)
    if awaits_resumed_coder(state):
        put_resumed_coder_back(repo_dir, state)
    elif awaits_resumed_review(state):
        put_resumed_review_back(repo_dir, state)
    return handback


def coder_flags(report):
    flagged = []
    for line in report.splitlines():
        mentions_open_point = re.search(r"\bambigu(ous|ity|ities)\b|open question", line, re.I)
        denies_open_point = re.search(r"\b(no|none)\b", line, re.I)
        if mentions_open_point and not denies_open_point:
            flagged.append(line.strip())
    return flagged


PLAN_IMPACT_HEADER = re.compile(r"^[ \t>*`_-]*PLAN-IMPACT[*`_]*:?[*`_]*[ \t]*$")
PLAN_IMPACT_KEY = re.compile(r"^[ \t>*`_-]*(?:assumed|found|changes)[*`_]*:", re.I)


def plan_impact_body(lines_after_header):
    # The indented lines, or lines that start with one of the three keys, under a PLAN-IMPACT header. Blank lines may
    # sit between the header and the first line.
    body = []
    for later in lines_after_header:
        if not later.strip():
            if body:
                break
            continue
        if later[0] in " \t":
            body.append(later.rstrip())
        elif PLAN_IMPACT_KEY.match(later):
            body.append("  " + later.strip())
        else:
            break
    return body


def plan_impact_block(report):
    # The block is the header line `PLAN-IMPACT:` (bold or backticked is fine) and the lines under it.
    lines = report.splitlines()
    for index, line in enumerate(lines):
        if not PLAN_IMPACT_HEADER.match(line):
            continue
        body = plan_impact_body(lines[index + 1:])
        if body:
            return "PLAN-IMPACT:\n" + "\n".join(body)
    if re.search(r"^PLAN-IMPACT:\s*yes\s*$", report, re.M):
        return "PLAN-IMPACT: yes (block not found in the report; read the report)"
    return None


def first_plan_impact(messages):
    for message in messages:
        block = plan_impact_block(message)
        if block:
            return block
    return None


ALREADY_DONE_LINE = re.compile(
    r"^[ \t>*`_-]*ALREADY-DONE[*`_]*:[ \t]*(?:ask[ \t]*)?(\d+)[ \t]*(?:—|–|--?)[ \t]*(.*)$", re.M
)


def already_done_ask_numbers(repo_dir, report):
    # The numbers of the asks the coder says need no edit. Each one counts only when its ALREADY-DONE line holds nothing
    # but a file:line (a closing period, comma or semicolon aside) and that file exists in the repo.
    numbers = set()
    for match in ALREADY_DONE_LINE.finditer(report):
        location = script_utils.PATH_LINE.fullmatch(match.group(2).strip().rstrip(".,;"))
        if location and (repo_dir / script_utils.normalize_path(location.group(1))).is_file():
            numbers.add(int(match.group(1)))
    return numbers


def every_accepted_ask_already_done(repo_dir, state, report):
    accepted_ask_numbers = set(range(1, len(state["acceptedAsks"]) + 1))
    return accepted_ask_numbers <= already_done_ask_numbers(repo_dir, report)


def why_by_file(report):
    grouped = {}
    for match in re.finditer(r"^WHY:\s*`?(\S+?)`?(?::|\s+)(\d+-\d+)\s*[—-]+\s*(.+)$", report, re.M):
        grouped.setdefault(match.group(1), []).append({"lines": match.group(2), "note": match.group(3).strip()})
    return grouped


def behavior_lines(report):
    found = [m.group(1).strip() for m in re.finditer(r"^BEHAVIOR:\s*(.+)$", report, re.M)]
    return [line for line in found if line.lower() != "none"]


def path_suffixes(path, min_parts=2):
    parts = path.split("/")
    return ["/".join(parts[start:]) for start in range(len(parts)) if len(parts) - start >= min(min_parts, len(parts))]


def resolve_report_paths(grouped, files):
    # Re-key a report's per-path dict to the changed files' full paths, matching on trailing path parts.
    resolved = {}
    for report_path, value in grouped.items():
        candidates = [name for name in files if name == report_path or name.endswith("/" + report_path)
                      or report_path.endswith("/" + name)]
        target = candidates[0] if len(candidates) == 1 else report_path
        resolved.setdefault(target, []).extend(value)
    return resolved


def change_line(report, path, files, fallback_behavior, is_new_file=False):
    # A report names a file's change on a bullet that starts with the path (or a trailing part of it).
    # Prose lines that only mention the path, and grouped "Created: a, b" lines, do not count.
    base_name = path.rsplit("/", 1)[-1]
    shares_base_name = any(name != path and name.rsplit("/", 1)[-1] == base_name for name in files)
    suffixes = sorted(path_suffixes(path) + ([] if shares_base_name else [base_name]), key=len, reverse=True)
    for line in report.splitlines():
        if not re.match(r"^\s*[-*]\s", line):
            continue
        body = line.strip().lstrip("-* ").lstrip("`")
        for suffix in suffixes:
            match = re.match(rf"{re.escape(suffix)}`?\s*(?:[:—-]+\s*|\s+)(.+)$", body)
            if match:
                return re.sub(r"\s+", " ", match.group(1).strip())[:160]
    if is_new_file:
        return "new file"
    return fallback_behavior or "changed by the coder"


def gate_results(repo_dir):
    gate_file = git_output(repo_dir, "rev-parse", "--path-format=absolute", "--git-path", "coder-gate.json")
    if gate_file is None or not pathlib.Path(gate_file).exists():
        return None
    return json.loads(pathlib.Path(gate_file).read_text())


def tests_run_text(gate, state):
    if gate is None or not gate["coders"]:
        return "none"
    parts = []
    for coder in gate["coders"].values():
        for command in gate["commands"]:
            if command in coder["failed"]:
                parts.append(f"{command} -> failed at the hand-back gate ({coder['result']})")
            elif command in coder.get("skipped", []):
                parts.append(f"{command} -> skipped, no changed files")
            else:
                parts.append(f"{command} -> exit 0")
    return "; ".join(parts)


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


def coder_changed_files(repo_dir, state, changed_now):
    # The files the phase changed since its baseline, and the files the coder committed itself.
    baseline = state["baseline"]
    changed_files = [name for name, digest in changed_now.items() if name not in baseline or baseline[name] != digest]
    committed = committed_since(repo_dir, state.get("baseHead"))
    return changed_files + [name for name in committed if name not in changed_files]


def unreviewable_outcome(repo_dir, state, report, changed_files, changed_now):
    # "converged" when the asks coder changed nothing and named, for each confirmed ask, the file:line that already
    # does it; "stop" for a report with no reviewable change or one that recommends /eng-spec; else None. Any other
    # report with no change (a failed edit, a blocked hook, a question) stops.
    is_ask_fix = state["stage"] == "asks-coder"
    asks_coder_changed_nothing = is_ask_fix and changed_now == state.get("asksBaseline")
    recommends_eng_spec = "/eng-spec" in report
    report_raises_blocker = recommends_eng_spec or bool(first_plan_impact([report])) or bool(coder_flags(report))
    if asks_coder_changed_nothing and not report_raises_blocker and every_accepted_ask_already_done(
            repo_dir, state, report):
        return "converged"
    if not changed_files or asks_coder_changed_nothing or recommends_eng_spec:
        return "stop"
    return None


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
    emit("stop", "The coder produced no reviewable change, or recommended /eng-spec. Do not dispatch a "
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
        behavior = list(state.get("behavior", [])) + behavior
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
    messages = [message for report in phase_coder_reports(repo_dir, state) if report["stage"] == coder_stage
                for message in report["attempts"] + report["messages"]]
    return first_plan_impact(messages)


def review_coder_report(repo_dir, state, handback):
    coder_stage = state["stage"]
    is_ask_fix = coder_stage == "asks-coder"
    report = handback.get("message", "")
    gate = None if is_ask_fix else gate_results(repo_dir)
    gate_lines = state.get("gateLines", "")
    if not is_ask_fix:
        _code, gate_lines = run_command(["python3", str(SCRIPTS_DIR / "code" / "coder_gate.py"), "clear"], repo_dir)
    state["flagged"] = coder_flagged(state, gate, report, is_ask_fix)

    changed_now = file_hashes(repo_dir)
    changed_files = coder_changed_files(repo_dir, state, changed_now)
    outcome = unreviewable_outcome(repo_dir, state, report, changed_files, changed_now)
    if outcome == "converged":
        return finish_without_review(
            repo_dir, state, changed_files, coder_stage,
            "The asks coder changed nothing, and named where each confirmed ask is already in the code. No review "
            "runs. The coder reported:\n" + report)
    if outcome == "stop":
        return stop_on_coder_report(repo_dir, state, report, handback.get("agent_id"))

    asks_baseline = state.get("asksBaseline")
    if is_ask_fix and asks_baseline is not None:
        # The review after an asks-coder covers only what the asks-coder changed. A state from before asksBaseline
        # existed keeps the whole-phase scope.
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


def prior_issues(accepted_asks):
    issues = []
    for item, _outcome, change_text in accepted_asks:
        file_line = item.get("file_line", "")
        issue_text = ask_text(item)
        if change_text:
            issue_text += f" (user's change: {change_text})"
        issues.append({"issue": issue_text, "file": file_line.partition(":")[0]})
    return issues


def ask_text(item):
    # The shared reader copies a finding into the question (and the reverse) when only one is given: show it once.
    return script_utils.joined_distinct([str(item.get("finding") or ""), str(item.get("question") or "")])


def numbered_ask_lines(asks):
    # Each ask with the one change an accepted answer makes.
    lines = []
    for number, item in enumerate(asks, 1):
        lines.append(f"{number}. {ask_text(item)}")
        if item.get("change"):
            lines.append(f"   Proposed change: {item['change']}")
    return lines


# ---------- plan impact ----------

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


def emit_plan_impact_modal(impact, repo_dir):
    word = preset_decision(repo_dir)
    if word:
        print(f"PLAN-IMPACT answered by the pre-set decision '{word}'. No question to the user.")
        state = load_state(repo_dir)
        return command_decide(repo_dir, state, [word, "--by", "session", "--ruling",
                                                f"pre-set decision '{word}'; no user was asked"],
                              ruling_by="the pre-set decision")
    ask_user(repo_dir, "the code and the plan disagree. Ask the user this question in plain text and wait for the "
             "answer. Then invoke Skill code with the args after the option the user chose, with the ruling in one "
             "line, in your own words, as the --ruling text. Do not quote the user.",
             impact, "",
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


DECIDE_USAGE = 'decide <adopt|keep> --by <user|session> --ruling "<the decision in one line>"'


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
        return f"decide {word} needs --by user or --by session. Usage: `{DECIDE_USAGE}`. {DECIDE_BY_NOTE}"
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
    if decision == PLAN_IMPACT_OPTIONS[0] and state.get("plan"):
        return emit_plan_edit_dispatch(repo_dir, state)
    emit_review_dispatch(repo_dir, state)


# ---------- plan edit ----------

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
    lines += ["", "Report each line you changed as `<file>:<line number>: <new text>`."]
    return "\n".join(lines)


def emit_plan_edit_dispatch(repo_dir, state):
    # An adopted change stays only in Plan Deviations unless the steps that contradict it change too, and the
    # reviewer then reads the old step and raises the same disagreement again.
    criteria_path = criteria_file(repo_dir, state)
    ruling = state["ruling"]
    if not ruling["byUser"]:
        save_criteria_guard(repo_dir, state)
    state.update({"stage": "plan-coder", "planEditBaseline": file_hashes(repo_dir),
                  "followUpBefore": change_snapshot(repo_dir)})
    open_dispatch(state)
    save_state(repo_dir, state)

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
    state.pop("stopReason", None)
    state.pop("resumableReview", None)
    state.pop("resumeWaitAt", None)
    # A failed review that ran the structure pass runs it again; one that skipped it skips it again.
    if not state.get("structurePassSkipped"):
        state.pop("reviewRan", None)
    emit_review_dispatch(repo_dir, state)


def command_after_plan_edit(repo_dir, state, args):
    if not wait_for_handback(repo_dir, state, RESUME_VERB):
        return
    state["sessionId"] = session_pin() or state.get("sessionId")

    had_criteria_guard = state.get("criteriaGuard") is not None
    criteria_message = settle_criteria_guard(repo_dir, state, branch_label(repo_dir))
    if criteria_message:
        say(repo_dir, criteria_message)

    if had_criteria_guard:
        save_state(repo_dir, state)

    baseline = state.pop("planEditBaseline")
    changed_now = file_hashes(repo_dir)
    edited_files = [name for name, digest in changed_now.items() if baseline.get(name) != digest]

    criteria_path = criteria_file(repo_dir, state)
    allowed_files = (state["plan"], criteria_path) if state["ruling"]["byUser"] else (state["plan"],)
    stray_files = [name for name in edited_files if name not in allowed_files]
    if stray_files:
        state["files"] += [name for name in stray_files if name not in state["files"]]
        state["flagged"].append("the plan-edit coder also changed " + ", ".join(stray_files))
        state["exception"] = True

    plan_lines = (repo_dir / state["plan"]).read_text().splitlines()
    state["phaseText"] = plan_format.phase_text(plan_lines, state["phase"])

    plan_note = f"The plan {state['plan']} now states the ruling."
    if criteria_path and criteria_path in edited_files and state["ruling"]["byUser"]:
        plan_note += f" The acceptance criteria in {criteria_path} changed too: read them before you stage."
    say(repo_dir, plan_note)

    emit_review_dispatch(repo_dir, state)


# ---------- review dispatch ----------

def handoff_block(state):
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
    lines.append(f"  tests-run: {state['testsRun']}")
    lines.append("  flagged: " + ("; ".join(state["flagged"]) if state["flagged"] else "none"))
    plan_impact = state.get("planImpact", "none")
    if plan_impact == "none":
        lines.append("  plan_impact: none")
    else:
        lines.append("  plan_impact: |")
        lines += ["    " + line for line in plan_impact.splitlines()]
    lines.append(f"  iter: {state.get('iter', 0)}")
    if state.get("spec_iter"):
        lines.append(f"  spec_iter: {state['spec_iter']}")
    return "\n".join(lines)


SMALL_FOLLOW_UP_LINES = 40
LOCKFILE_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock", "Cargo.lock",
                  "Gemfile.lock", "composer.lock", "go.sum", "bun.lockb"}


def is_test_path(path):
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    parts = lowered.split("/")[:-1]
    return (any(part in ("test", "tests", "__tests__", "spec", "specs") for part in parts)
            or name.startswith("test_") or ".test." in name or ".spec." in name or "_test." in name)


def is_uncounted_path(path):
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    return (path.rsplit("/", 1)[-1] in LOCKFILE_NAMES or name.endswith(".lock") or "__snapshots__" in lowered
            or name.endswith(".snap") or "generated" in lowered or ".generated." in name or ".gen." in name
            or name.endswith(".min.js"))


def is_counted_source(path):
    return not is_test_path(path) and not is_uncounted_path(path)


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
    last_messages = [report["messages"][-1] for report in phase_coder_reports(repo_dir, state)
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
    header = ["mode: review-first", "caller: code", f"lane: {state['lane']}"]
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
    prompt = "\n".join(header) + "\n\n" + handoff_block(state)
    state["stage"] = "review"
    open_dispatch(state)
    state["lastReviewPrompt"] = prompt
    save_state(repo_dir, state)

    summary = ["Implemented: " + ("; ".join(state["behavior"]) or "see the diff.")]
    summary.append("Flagged: " + ("; ".join(state["flagged"]) if state["flagged"] else "none."))
    for path, notes in state["why"].items():
        summary += [f"  {path}:{note['lines']} - {note['note']}" for note in notes]
    summary.append("Auto-dispatching review to check the implementation before committing.")
    say(repo_dir, "\n".join(summary))
    emit_dispatch(repo_dir, state, RESUME_VERB, prompt=prompt, agent="review-loop", model="sonnet")


# ---------- review ----------

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


def stop_on_review_status(repo_dir, state, module, packet):
    # True after the stop or question a packet status that ends the run prints.
    status = packet["status"]
    if status == "plan-impact":
        state.update({"stage": "impact-review", "impact": packet["plan_impact"]})
        save_state(repo_dir, state)
        emit_plan_impact_modal(state["impact"], repo_dir)
        return True
    if status == "critical-blocker":
        state["stage"] = "stopped"
        save_state(repo_dir, state)
        emit("stop", "Review found a critical blocker. Present these to the user. Do not mark the phase done.",
             *["- " + module.item_text(item, "finding", "file_line") for item in packet["blockers"]])
        return True
    if status == "cap-reached":
        state["stage"] = "stopped"
        save_state(repo_dir, state)
        emit("stop", "The review cap was reached. Report these findings to the user. Do not mark the phase "
             "done. The session stays dirty, so git commit stays blocked.",
             *["- " + module.item_text(item, "finding", "file_line") for item in packet["findings_remaining"]])
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
    if stop_on_review_status(repo_dir, state, module, packet):
        return

    save_state(repo_dir, state)
    say(repo_dir, module.render(packet, "code"))
    print("The review packet was saved for the user. Do not repeat it.")
    asks = packet["ask"]
    if asks:
        return present_asks(repo_dir, state, asks)
    finish_phase(repo_dir, state)


# ---------- asks ----------

ASK_OUTCOMES = ("accepted", "rejected", "modified")


def preset_ask_outcome(repo_dir):
    # A pre-answered outcome for every review ask, for runs with no user (claude -p, bench): env var or a file in the
    # state dir.
    word = os.environ.get("CODE_STEP_ASKS_OUTCOME", "").strip().lower()
    preset_file = state_dir(repo_dir) / "asks-outcome"
    if not word and preset_file.exists():
        word = preset_file.read_text().strip().lower()
    return word if word in ASK_OUTCOMES else None


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
        log_ask_outcomes(repo_dir, state, [preset_outcome] * len(asks))
        return apply_asks_or_finish(repo_dir, state, [preset_outcome] * len(asks), [None] * len(asks))
    ask_the_user(repo_dir, state, asks)


def ask_the_user(repo_dir, state, asks):
    if not mark_review_gate_clean(repo_dir, state):
        state["stage"] = "stopped"
        save_state(repo_dir, state)
        return
    state["stage"] = "asks"
    save_state(repo_dir, state)
    ask_user(
        repo_dir,
        f"ask the user about each review ask below in plain text and wait for the answers. Each answer is accepted "
        f"(make the proposed change), rejected (leave the code as it stands) or modified (make the user's change "
        f"instead). Then invoke Skill code with the args `asks-done` and {len(asks)} outcome word(s), in order. After "
        "a modified outcome, add `--change \"<the user's change text>\"`.",
        *numbered_ask_lines(asks),
    )


def log_ask_outcomes(repo_dir, state, outcomes):
    module, import_error = load_handback()
    if module is None:
        print(f"code-step: ask outcomes not logged: {import_error}", file=sys.stderr)
        return

    branch = git_output(repo_dir, "branch", "--show-current") or "-"
    for item, outcome in zip(state["asks"], outcomes, strict=False):
        finding_id = module.ask_finding_id(item)
        if finding_id is None:
            # The outcome supersedes its ask row by finding_id. Only an id the ledger writer mints replaces a row:
            # a placeholder such as "none" or a damaged id would add a second finding.
            ignored_value = item.get("finding_id")
            ignored_text = "no finding_id" if ignored_value is None else f"ignored {ignored_value!r}"
            print(f"code-step: ask outcome without a valid finding_id ({ignored_text}), not logged", file=sys.stderr)
            continue

        file_line = item.get("file_line", "-:0")
        path, _, line = file_line.partition(":")
        # The writer takes phase as a token, so a run with no phase sends none.
        phase_args = [f"phase={state['phase']}"] if state.get("phase") else []
        logger_code, logger_output = run_command(
            ["bash", str(CLAUDE_DIR / "skills/review/log-review-finding"), "kind=finding",
             f"finding_id={finding_id}", f"branch={branch}", f"lane={state['lane']}", "scope=phase",
             *phase_args, f"iter={state['iter']}",
             f"gate={item.get('gate', 'code-reviewer')}",
             "disposition=ask", f"class={item.get('class', 'other')}", f"file={path}",
             f"line={re.sub(r'[^0-9].*', '', line) or '0'}", "actioned=ask", f"ask_outcome={outcome}"], repo_dir)
        if logger_code != 0:
            print(f"code-step: ask outcome for finding_id {finding_id} not logged: log-review-finding exited "
                  f"{logger_code}: {script_utils.one_line(logger_output)}", file=sys.stderr)


def asks_coder_prompt(accepted_asks):
    lines = ["Apply these review asks. The user accepted them. Make the change each one names and nothing else.", ""]
    for number, (item, outcome, change_text) in enumerate(accepted_asks, 1):
        location = item.get("file_line", "")
        lines.append(f"{number}. [{outcome}] {ask_text(item)}"
                     + (f" ({location})" if location else ""))
        if change_text:
            lines.append(f"   The user's change: {change_text}")
        elif item.get("change"):
            lines.append(f"   The proposed change: {item['change']}")
    lines += [
        "",
        "Run the typecheck, and lint and tests for only the files you changed, once, after all edits. "
        "If an ask turns out architectural, report back and recommend /eng-spec.",
        "For each ask whose change the code already makes, so that it needs no edit, add one line to your report: "
        "`ALREADY-DONE: <ask number> — <file:line>`. Add that line for no other ask.",
    ]
    return "\n".join(lines)


def apply_asks_or_finish(repo_dir, state, outcomes, change_texts):
    # An accepted or modified ask is owed work: a coder applies it, then a review of that coder's diff runs (none when
    # the diff is docs only) before the phase can finish.
    accepted_asks = [
        [item, outcome, change_text]
        for item, outcome, change_text in zip(state["asks"], outcomes, change_texts, strict=False)
        if outcome != "rejected"
    ]
    if not accepted_asks:
        state["stage"] = "review"
        save_state(repo_dir, state)
        return finish_phase(repo_dir, state)

    state.update({"stage": "asks-coder", "acceptedAsks": accepted_asks, "asksApplied": True,
                  "asksBaseline": file_hashes(repo_dir), "followUpBefore": change_snapshot(repo_dir)})
    open_dispatch(state)
    save_state(repo_dir, state)
    model = "haiku" if state.get("modifier") == "+fast" else None
    emit_dispatch(repo_dir, state, RESUME_VERB, "The user accepted review asks. Dispatch a coder to apply them. A "
                  "review of that coder's diff runs after it (none when the diff is docs only) before the phase can "
                  "finish.", prompt=asks_coder_prompt(accepted_asks), agent="coder", model=model)


def split_asks_done_args(args):
    # Outcome words in order, and the text after each `--change` flag, one per modified ask, in order.
    outcomes = []
    change_texts = []
    position = 0
    while position < len(args):
        if args[position] == "--change":
            if position + 1 >= len(args):
                return outcomes, None
            change_texts.append(args[position + 1])
            position += 2
            continue
        outcomes.append(args[position])
        position += 1
    return outcomes, change_texts


def command_asks_done(repo_dir, state, args):
    outcomes, given_changes = split_asks_done_args(args)
    if len(outcomes) != len(state["asks"]) \
            or any(outcome not in ASK_OUTCOMES for outcome in outcomes) or given_changes is None \
            or len(given_changes) != outcomes.count("modified"):
        return emit("stop", ASKS_DONE_USAGE)

    remaining_changes = iter(given_changes)
    change_texts = [next(remaining_changes) if outcome == "modified" else None for outcome in outcomes]
    log_ask_outcomes(repo_dir, state, outcomes)
    apply_asks_or_finish(repo_dir, state, outcomes, change_texts)


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
    # The user resumed the review-loop that the wait cap stopped on.
    launch_id = awaited_agent_id(repo_dir, state)
    return launch_id is not None and sent_message_since(repo_dir, state, state["resumableReview"], launch_id)


def stopped_route(repo_dir, state):
    if awaits_resumed_coder(state):
        return "after-coder" if coder_answer_sent(repo_dir, state) else "ask-coder"
    if awaits_resumed_review(state):
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
    emit_closing_skill(state["phase"], state["title"], skill, section)


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
    emit_plan_impact_modal(state["impact"], repo_dir)


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
    # Only a coder that waits for the user's answer takes one: `resume <answer>`.
    if args and route != "ask-coder":
        return refuse("resume takes no arguments here: no stopped coder waits for an answer.",
                      script_command(RESUME_VERB), notes=("For new work, use `start --task \"<text>\"`.",))

    if state is not None and (state["stage"] == "stopped" or state["stage"] in WAITING_STAGES):
        clear_say(repo_dir)

    if args:
        return ask_about_stopped_coder(repo_dir, state, answer=" ".join(args))
    RESUME_HANDLERS.get(route, ask_about_unrecorded_state)(repo_dir, state)


def command_status():
    state = load_state(repo_root_or_exit())
    print(json.dumps(state, indent=1) if state else "no code-step state")


def run_status():
    try:
        command_status()
    except StateFileError as error:
        print(error)


HOOK_VERBS = {
    "hook": command_hook, "log-hook": command_log_hook, "dispatch-hook": command_dispatch_hook,
    "plan-hook": command_plan_hook, "stop-hook": command_stop_hook, "say-hook": command_say_hook,
}
VERB_USAGE = ("usage: code_step.py start|resume|decide|asks-done|skill-done|verify|review-again|tick|hook|log-hook"
              "|dispatch-hook|stop-hook|say-hook|status|plan|plan-hook")


def run_verb(verb, handler, args):
    clear_question(repo_root_or_exit())
    if verb in VERBS_THAT_CLEAR_SAY:
        clear_say(repo_root_or_exit())
    try:
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
             "asks-done": command_asks_done, "skill-done": command_skill_done, "verify": command_verify,
             "tick": command_tick, "review-again": command_review_again}
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
