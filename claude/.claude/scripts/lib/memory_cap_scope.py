"""Whether a Bash command starts a test run outside a memory-capped scope, and the capped form to run instead.

A test run that allocates without bound takes the whole machine's memory and the kernel ends every session on it. A
run inside `systemd-run --user --scope -p MemoryMax=... -p MemorySwapMax=0` dies alone at the cap. uncapped_test_run
names such a command: a step that runs tests (check_scope.step_runs_tests) or `tests/run.sh`, with no systemd-run
wrapper in front of it. A step that asks for usage (`--help`, `-h`, `--version`) runs nothing and is not one. A
command text that shlex cannot split is not one either. cap_available says whether this machine can run the scope:
Linux, systemd-run on PATH and a user bus."""
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


def cap_available():
    """True on a machine that can run a systemd user scope."""
    if not sys.platform.startswith("linux") or shutil.which("systemd-run") is None:
        return False
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    return bool(runtime_dir) and os.path.exists(os.path.join(runtime_dir, "bus"))


def runs_test_script(words):
    """True when the step runs tests/run.sh, directly or through a shell."""
    if not words:
        return False
    if RUN_SCRIPT.search(words[0]):
        return True
    return os.path.basename(words[0]) in SHELLS and len(words) > 1 and bool(RUN_SCRIPT.search(words[1]))


def step_is_uncapped_test_run(words):
    words = shell_command.without_assignments(words)
    if not words or HELP_FLAGS.intersection(words):
        return False

    wrapper_names = shell_command.wrapper_chain(words)
    if "systemd-run" in wrapper_names:
        return False

    import check_scope  # pylint: disable=import-outside-toplevel

    final_words = shell_command.command_after_wrappers(words)
    return check_scope.step_runs_tests(final_words) or runs_test_script(final_words)


def uncapped_test_run(command):
    if not TEST_WORDS.search(command):
        return False
    try:
        steps = shell_command.split_simple_commands(command)
    except ValueError:
        return False
    return any(step_is_uncapped_test_run(words) for words in steps)
