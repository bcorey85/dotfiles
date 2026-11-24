"""Whether a Bash command starts a test run outside a memory-capped scope, and the capped form to run instead.

A test run that allocates without bound takes the whole machine's memory and the kernel ends every session on it. A
run inside `systemd-run --user --scope -p MemoryMax=... -p MemorySwapMax=0` dies alone at the cap. uncapped_test_run
names such a command: a step that runs tests (check_scope.step_runs_tests), `tests/run.sh`, or a test program named
by a path (`./pytest`), with no systemd-run wrapper in front of it. A step that asks for usage (`--help`, `-h`,
`--version`, `-V`) runs nothing and is not one. A command text that shlex cannot split is not one either.
cap_available says whether this machine can run the scope: Linux, systemd-run on PATH and a user bus.

is_rewritable_test_run names the one case the hook fixes itself: the whole command is a single plain step that runs
a test runner or the repo's tests/run.sh, and capped_command puts CAPPED_PREFIX in front of it. The hook denies other
uncapped test runs with DENY_TEXT; gates/inline_interpreter_hint.py says which deny answers first.

foreground_full_suite names a command with a full-suite step (tests/run.sh, `unittest discover`, a bare runner),
capped or not: a main session's tool call must run it with run_in_background so the conversation stays open. A run
of one or a few named test files is not one."""
import os
import re
import shutil
import sys

import shell_command

MEMORY_MAX = "8G"
CAPPED_PREFIX = f"systemd-run --user --scope --quiet -p MemoryMax={MEMORY_MAX} -p MemorySwapMax=0"
SHELLS = {"bash", "sh", "zsh"}
RUN_SCRIPT = re.compile(r"(^|/)tests/run\.sh$")
# A command that holds none of these words runs no test: skip the heavy check_scope import for it.
TEST_WORDS = re.compile(r"test|jest|mocha|run\.sh", re.I)
HELP_FLAGS = {"--help", "-h", "--version", "-V"}
DENY_TEXT = (f"A test run outside a memory cap can take all the memory on this machine and end every session on it. "
             f"Put `{CAPPED_PREFIX}` in front of the test program in each test step, for example "
             f"`{CAPPED_PREFIX} python3 -m unittest discover | tail -20` or "
             f"`{CAPPED_PREFIX} bash tests/run.sh`. A run that goes past {MEMORY_MAX} is then killed alone and "
             f"your session survives.")
BACKGROUND_DENY_TEXT = (f"A full test suite in the foreground blocks the conversation until it ends. Rerun the same "
                        f"command with the Bash tool's run_in_background set to true, inside the cap "
                        f"(`{CAPPED_PREFIX} <test command>`), then go on with other work or end the turn until the "
                        f"completion notice arrives. A run of one or a few named test files may stay in the "
                        f"foreground.")
SYSTEMD_RUN_VALUE_OPTIONS = {"-p", "--property", "-u", "--unit", "--slice", "-E", "--setenv"}


def cap_available():
    """True on a machine that can run a systemd user scope."""
    if not sys.platform.startswith("linux") or shutil.which("systemd-run") is None:
        return False
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    return bool(runtime_dir) and os.path.exists(os.path.join(runtime_dir, "bus"))


def runs_test_script(words):
    """True when the step runs tests/run.sh, directly or through a shell."""
    script_word = run_script_word(words)
    return script_word is not None and bool(RUN_SCRIPT.search(script_word))


def run_script_word(words):
    """The word that would be tests/run.sh: the program word, or the word after a shell. None when there is none."""
    if not words:
        return None
    if os.path.basename(words[0]) in SHELLS:
        return words[1] if len(words) > 1 else None
    return words[0]


def step_is_uncapped_test_run(words):
    words = shell_command.without_assignments(words)
    if not words or HELP_FLAGS.intersection(words):
        return False

    wrapper_names = shell_command.wrapper_chain(words)
    if "systemd-run" in wrapper_names:
        return False

    import check_scope  # pylint: disable=import-outside-toplevel

    final_words = shell_command.command_after_wrappers(words)
    return (check_scope.step_runs_tests(final_words) or runs_test_script(final_words)
            or check_scope.path_program_runs_tests(final_words))


def is_own_tests_path(word, name):
    """True when the word names the repo's own tests/<name> by a relative path (`tests/<name>`, `./tests/<name>`)."""
    return word in (f"tests/{name}", f"./tests/{name}")


def uncapped_test_run(command):
    if not TEST_WORDS.search(command):
        return False
    try:
        steps = shell_command.split_simple_commands(command)
    except ValueError:
        return False
    return any(step_is_uncapped_test_run(words) for words in steps)


def capped_command(command):
    """The command with the capped prefix in front of it."""
    return f"{CAPPED_PREFIX} {command}"


def is_rewritable_test_run(command):
    """True when the whole command is one plain simple command whose program word is a test runner, so the capped
    prefix in front of it changes nothing else: no wrapper word (`sudo`, `exec`, `time`, `env`), operator, newline,
    subshell, brace group, substitution, redirection, heredoc or leading NAME=value word, and no usage flag. A path
    is accepted only for the repo's own tests/run.sh (`tests/run.sh` or `./tests/run.sh`, alone or after a shell)
    and tests/parallel_tests.py (`tests/parallel_tests.py` or `./tests/parallel_tests.py`, after a python program):
    a program word with any other `/` and a run script or runner script at any other path are False. The caller
    sends the rewritten command back for the normal permission check, so any doubt is False."""
    if not TEST_WORDS.search(command):
        return False
    if shell_command.substitution_spans(command):
        return False

    try:
        steps = shell_command.split_command_steps(command)
        parsed_commands = shell_command.parse_piped_commands(command)
    except ValueError:
        return False
    # One step: no chain, background `&`, newline or heredoc body. One parsed command: no pipe and no `(`/`)` between
    # words.
    if len(steps) != 1 or len(parsed_commands) != 1:
        return False

    words, redirections, _piped = parsed_commands[0]
    if redirections or shell_command.without_assignments(words) != words:
        return False
    if not words or HELP_FLAGS.intersection(words):
        return False
    # A shell or program named by a path may not be the real one: only tests/run.sh itself may be a path.
    if "/" in words[0] and not is_own_tests_path(words[0], "run.sh"):
        return False
    script_word = run_script_word(words)
    names_other_run_script = (
        script_word is not None and RUN_SCRIPT.search(script_word) and not is_own_tests_path(script_word, "run.sh")
    )
    if names_other_run_script:
        return False

    import check_scope  # pylint: disable=import-outside-toplevel
    import shell_steps  # pylint: disable=import-outside-toplevel

    runs_runner_script = check_scope.step_runs_test_runner_script(words)
    if runs_runner_script and not is_own_tests_path(words[1], check_scope.TEST_RUNNER_SCRIPT):
        return False

    step_text = steps[0][1]
    if shell_steps.group_closes(step_text)[0] or shell_steps.group_depth_change(step_text) != 0:
        return False

    return check_scope.program_runs_tests(words) or runs_test_script(words)


def program_after_systemd_run(words):
    """The words of the program a `systemd-run` step runs, or the words unchanged for any other step."""
    if os.path.basename(words[0]) != "systemd-run":
        return words

    index = 1
    while index < len(words) and words[index].startswith("-"):
        index += 2 if words[index] in SYSTEMD_RUN_VALUE_OPTIONS else 1
    return words[index:]


def is_full_unittest_run(words):
    """True for `python -m unittest` with no module name, or with `discover` (whatever directory or pattern)."""
    if len(words) < 3 or words[1:3] != ["-m", "unittest"]:
        return False

    positional_words = [word for word in words[3:] if not word.startswith("-")]
    return not positional_words or positional_words[0] == "discover"


def step_is_full_suite(words):
    words = shell_command.without_assignments(words)
    if not words or HELP_FLAGS.intersection(words):
        return False

    final_words = program_after_systemd_run(shell_command.command_after_wrappers(words))
    if not final_words:
        return False

    if runs_test_script(final_words):
        return True

    import check_scope  # pylint: disable=import-outside-toplevel

    if not check_scope.step_runs_tests(final_words):
        return False

    if os.path.basename(final_words[0]).startswith("python"):
        final_words = ["python", *final_words[1:]]
    return is_full_unittest_run(final_words) or check_scope.direct_check_scope(final_words) == "whole"


def foreground_full_suite(command):
    """True when the command has a full-suite test step. The caller has checked the call is not in the background."""
    if not TEST_WORDS.search(command):
        return False
    try:
        steps = shell_command.split_simple_commands(command)
    except ValueError:
        return False
    return any(step_is_full_suite(words) for words in steps)
