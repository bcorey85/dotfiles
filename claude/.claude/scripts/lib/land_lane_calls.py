"""Whether a Bash command runs tools/land_lane.py.

land_lane.py pushes to master from inside Python, so no git gate sees the push. Only the user runs it, as a `!` line;
a session's call that runs it is denied. A step runs it when its command, after wrappers (env, nice, timeout,
systemd-run, ...), is the script itself or a Python interpreter whose first non-option word is the script, or when
xargs, a shell `-c` text or an eval runs such a command. A word that
only mentions it (an echo or grep argument, a `cat` or `rg` of the file, a heredoc body, a test file named after it)
runs nothing.
"""
import os

import memory_cap_scope
import shell_command
import shell_statements

SCRIPT_NAME = "land_lane.py"
LAUNCHERS_WITH_OPTIONS = ("xargs",)
# xargs options that take the next word as their value.
XARGS_VALUE_OPTIONS = {"-I", "-n", "-P", "-d", "-E", "-L", "-s", "-a", "--max-args", "--max-procs", "--delimiter",
                       "--arg-file", "--max-lines", "--max-chars", "--replace"}


def program_words(words):
    """The words of the program a step finally runs, past its wrappers and a systemd-run in front of it."""
    after_wrappers = shell_command.command_after_wrappers(words)
    after_systemd = memory_cap_scope.program_after_systemd_run(after_wrappers)
    return shell_command.command_after_wrappers(after_systemd)


def names_script(word):
    return os.path.basename(word) == SCRIPT_NAME


def program_runs_script(program):
    """True when the program is land_lane.py, or a Python interpreter whose first non-option word is that script."""
    if names_script(program[0]):
        return True
    family = shell_command.interpreter_family(program[0])
    if family != "python":
        return False
    value_options = shell_command.INTERPRETER_FAMILIES[family]["value_options"]
    script_index = shell_command.skip_options(program, 1, value_options)
    return script_index < len(program) and names_script(program[script_index])


def launched_words(program):
    """The words a launcher (xargs) runs, past its own options; empty when the program is no launcher."""
    if os.path.basename(program[0]) not in LAUNCHERS_WITH_OPTIONS:
        return []
    return program[shell_command.skip_options(program, 1, XARGS_VALUE_OPTIONS):]


def step_runs_land_lane(words):
    """True when the step's program is land_lane.py, run directly, as the script of a Python interpreter, through a
    launcher, or in the command text of a shell `-c` or an eval."""
    program = program_words(words)
    if not program:
        return False
    if program_runs_script(program):
        return True
    launched = launched_words(program)
    if launched and step_runs_land_lane(launched):
        return True
    nested_code = shell_command.nested_code_text(program)
    return nested_code is not None and runs_land_lane(nested_code)


def runs_land_lane(command):
    """True when a step of the command runs land_lane.py. Text shlex cannot read is cut on its operators and split on
    blanks, so a step is still read."""
    code = shell_statements.shell_code(command)
    return any(step_runs_land_lane(words) for words in shell_command.step_words(code))
