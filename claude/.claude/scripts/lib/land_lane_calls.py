"""Whether a Bash command runs tools/land_lane.py.

land_lane.py pushes to master from inside Python, so no git gate sees the push. Only the user runs it, as a `!` line;
a session's call that runs it is denied. A step runs it when its command, after wrappers (env, nice, timeout,
systemd-run, ...), is the script itself or a Python interpreter whose first non-option word is the script. A word that
only mentions it (an echo or grep argument, a `cat` or `rg` of the file, a heredoc body, a test file named after it)
runs nothing.
"""
import os

import memory_cap_scope
import shell_command
import shell_statements

SCRIPT_NAME = "land_lane.py"


def program_words(words):
    """The words of the program a step finally runs, past its wrappers and a systemd-run in front of it."""
    after_wrappers = shell_command.command_after_wrappers(words)
    after_systemd = memory_cap_scope.program_after_systemd_run(after_wrappers)
    return shell_command.command_after_wrappers(after_systemd)


def names_script(word):
    return os.path.basename(word) == SCRIPT_NAME


def step_runs_land_lane(words):
    """True when the step's program is land_lane.py, run directly or as the script of a Python interpreter."""
    program = program_words(words)
    if not program:
        return False
    if names_script(program[0]):
        return True
    if shell_command.interpreter_family(program[0]) != "python":
        return False
    script_words = [word for word in program[1:] if not word.startswith("-")]
    return bool(script_words) and names_script(script_words[0])


def runs_land_lane(command):
    """True when a step of the command runs land_lane.py. Text shlex cannot read is cut on its operators and split on
    blanks, so a step is still read."""
    code = shell_statements.shell_code(command)
    return any(step_runs_land_lane(words) for words in shell_command.step_words(code))
