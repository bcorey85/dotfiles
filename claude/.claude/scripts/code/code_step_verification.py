"""code_step_verification.py: reads a phase's Automated Verification items, checks that each can run, and runs them.

It imports only code_step_core of the code_step modules."""
import os
import pathlib
import re
import shutil

import plan_format
import script_utils
import shell_command
from code_step_core import SCRIPTS_DIR, branch_label
from criteria_verdict import item_verdict, without_leading_cd_and_env, without_negation
from script_utils import run_command

VERIFY_TIMEOUT_SECONDS = 600
COMMAND_START = re.compile(r"^(?:" + script_utils.ENV_PREFIX.pattern + r")?"
                           r"(cd |npm |npx |pnpm |yarn |git |node |python3? |pytest|ruff |bash |curl |make "
                           r"|cargo |go |deno |bun |uv |poetry |pipenv |pdm |tsc\b|eslint |vitest|jest|mvn |gradle |\./"
                           r"|dotnet |docker |just |rake |bundle |ruby |php |composer |mix |swift |sbt |bazel |tox\b"
                           r"|mypy |pyright|sh )")
# Programs that a prose span can start with but that are never a check: they start a session, never end or wait for
# input. `tail` is one only when it follows a file (see TAIL_FOLLOWS).
NOT_A_CHECK_PROGRAMS = ("claude", "yes", "watch", "top", "htop", "less", "more", "vi", "vim", "nano", "sleep")
TAIL_FOLLOWS = re.compile(r"^(?:-[A-Za-z0-9]*[fF][A-Za-z0-9]*|--follow(?:=\w+)?)$")
# A shell run on a code string (`sh -c '...'`, `bash -ec '...'`) is not a check command: see hands_a_shell_its_code.
SHELL_CODE_PROBLEM = ("it hands a shell its code with `-c`, which the plan format forbids (the shell hook also blocks "
                      "it when run by hand); write the command plainly, or put the pipeline in an executable repo "
                      "script and run `path/to/script args`")
VERIFICATION_ITEM_SHAPE = (
    "Each Automated Verification item is one line in one of three shapes. (1) One backticked command that starts with "
    "a program on PATH (with at least one argument) or an executable file in the repo, for example the line "
    "'- [ ] **Name**: what it checks - `npm test`'. A check that needs a variable assignment, `&&`, a pipe or a "
    "subshell goes in an executable repo script, run as `path/to/script args`; the script's comments name no ticket "
    "or plan path. Never wrap a command in `sh -c` or `bash -c`. (2) N/A, for example '- [ ] N/A - docs only'. "
    "(3) A tag that says CI, a person, or an agent runs it, for example '- [ ] **CI-verified**: the pipeline runs "
    "it', '- [ ] Human-only: look at the page' or '- [ ] **Agent-run**: time the import on the real data'. This "
    "script never runs the third shape.")


def deferred_verification_items(phase_section):
    # (tag, item text) for each Automated Verification item the plan leaves to CI, a person, or an agent (Agent-run),
    # in file order.
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


def first_command_span(line, repo_dir):
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


def hands_a_shell_its_code(span):
    # True when the span runs a shell on a code string, as `sh -c '...'`, `bash -euo pipefail -c '...'` or
    # `timeout 60 bash -c '...'`.
    command = without_leading_cd_and_env(span)
    words = shell_command.segment_words(command)
    code = shell_command.shell_code_argument(words)

    return code is not None


def verification_command(line, repo_dir=None):
    # The command an Automated Verification item runs, or None when it names none. A command that hands a shell its
    # code is none: the runner already runs each command in a shell, and the shell hook blocks the wrapper wherever
    # the command is run by hand.
    span = first_command_span(line, repo_dir)
    if span is None or hands_a_shell_its_code(span):
        return None
    return span


def verification_item_problem(line, repo_dir):
    # Why an Automated Verification item cannot run, or None when it runs, says there is nothing to run or is left to
    # CI or a person. The write-time check of a plan and the stop after a phase use this one reading.
    if plan_format.runs_no_command(line):
        return None

    span = first_command_span(line, repo_dir)
    if span is not None and hands_a_shell_its_code(span):
        return SHELL_CODE_PROBLEM
    if span is not None:
        return None

    spans = script_utils.backticked_spans(line)
    if not spans:
        return "it has no backticked command and is not marked N/A, CI-verified, human-only or agent-run"

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


def log_prohibition_scan(repo_dir, command, verdict):
    run_command(["bash", str(SCRIPTS_DIR / "telemetry" / "log-scan"), f"repo={repo_dir.name}", "scan=prohibition",
                 "stage=code-phase", f"exit={verdict.code}", f"candidates={verdict.hits}",
                 f"confirmed={verdict.hits}", f"branch={branch_label(repo_dir)}", f"note={command[:120]}"], repo_dir)


def run_verification_commands(repo_dir, phase_section, run_whole_suites=False):
    # The repo's configured `Quality check:` command is left to the review loop's own run unless the caller says
    # nothing else will run it. Every other command runs, and a repo with no configured check skips nothing.
    results = []
    skipped = []
    unparsed = []
    timeout = int(os.environ.get("CODE_STEP_VERIFY_TIMEOUT", VERIFY_TIMEOUT_SECONDS))
    # Imported here: review/ joins sys.path when code_step_core loads, which sorted top-level imports would precede.
    import full_check
    configured_check = full_check.configured_check_command(repo_dir)
    for _, line in plan_format.automated_verification_rows(phase_section.splitlines()):
        if plan_format.runs_no_command(line):
            continue
        command = verification_command(line, repo_dir)
        if command is None:
            unparsed.append(line.strip())
            continue
        is_configured_check_command = full_check.is_configured_check(command, configured_check)
        if is_configured_check_command and not run_whole_suites:
            skipped.append(command)
            continue
        code, output = run_command(command, repo_dir, timeout=timeout)
        verdict = item_verdict(command, line, code, output)
        if verdict.hits is not None:
            log_prohibition_scan(repo_dir, command, verdict)
        results.append((command, verdict.code, verdict.output))
    return results, skipped, unparsed
