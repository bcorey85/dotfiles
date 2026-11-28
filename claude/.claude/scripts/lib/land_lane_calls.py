"""Whether a Bash command runs tools/land_lane.py.

land_lane.py pushes to master from inside Python, so no git gate sees the push. Only the user runs it, as a `!` line;
a session's call that runs it is denied. A step runs it when its command, after wrappers (env, nice, timeout,
systemd-run, ...), is the script itself or a Python interpreter whose first non-option word is the script or
`-m land_lane`, or when a launcher (xargs, parallel, watch, flock, find -exec), a shell `-c` text, an ssh command
text or an eval runs such a command. A word that
only mentions it (an echo or grep argument, a `cat` or `rg` of the file, a heredoc body, a test file named after it)
runs nothing.
"""
import os

import memory_cap_scope
import shell_command
import shell_statements

SCRIPT_NAME = "land_lane.py"
MODULE_NAME = "land_lane"
EXEC_WORDS = ("-exec", "-execdir")


def program_words(words):
    """The words of the program a step finally runs, past its wrappers and a systemd-run in front of it."""
    after_wrappers = shell_command.command_after_wrappers(words)
    after_systemd = memory_cap_scope.program_after_systemd_run(after_wrappers)
    return shell_command.command_after_wrappers(after_systemd)


def names_script(word):
    return os.path.basename(word) == SCRIPT_NAME


def program_runs_script(program):
    """True when the program is land_lane.py, or a Python interpreter whose first non-option word is that script or
    is the module name after `-m`."""
    if names_script(program[0]):
        return True
    family = shell_command.interpreter_family(program[0])
    if family != "python":
        return False
    value_options = shell_command.INTERPRETER_FAMILIES[family]["value_options"]
    script_index = shell_command.skip_options(program, 1, value_options)
    if script_index >= len(program):
        return False
    if names_script(program[script_index]):
        return True
    return program[script_index - 1] == "-m" and program[script_index] == MODULE_NAME


def launched_command_starts(program):
    """The indexes in a launcher's words where the command it runs may start: each Python interpreter word, the first
    word that is no option, and the word after each `-exec` or `-execdir`. Empty when the program is no launcher.
    Only these may be the script itself, so `xargs rg land_lane.py` names the script as an argument and runs nothing."""
    if not shell_command.runs_through_launcher(program):
        return []
    starts = []
    for index in range(1, len(program)):
        word = program[index]
        follows_exec = program[index - 1] in EXEC_WORDS
        first_plain = not word.startswith("-") and not starts_before(program, index)
        is_python = shell_command.interpreter_family(word) == "python"
        if follows_exec or first_plain or is_python:
            starts.append(index)
    return starts


def starts_before(program, index):
    """True when a word before index in program (past the launcher word) is no option."""
    return any(not word.startswith("-") for word in program[1:index])


def launched_runs_land_lane(program):
    """True when a command a launcher runs is land_lane.py, run through step_runs_land_lane's forms."""
    for index in launched_command_starts(program):
        if program_runs_script(program[index:]):
            return True
        nested_code = shell_command.nested_code_text(program[index:])
        if nested_code is not None and runs_land_lane(nested_code):
            return True
    return False


def step_runs_land_lane(words):
    """True when the step's program is land_lane.py, run directly, as the script of a Python interpreter, through a
    launcher, or in the command text of a shell `-c` or an eval."""
    program = program_words(words)
    if not program:
        return False
    if program_runs_script(program):
        return True
    if launched_runs_land_lane(program):
        return True
    nested_code = shell_command.nested_code_text(program)
    return nested_code is not None and runs_land_lane(nested_code)


def runs_land_lane(command):
    """True when a step of the command runs land_lane.py. Text shlex cannot read is cut on its operators and split on
    blanks, so a step is still read."""
    code = shell_statements.shell_code(command)
    return any(step_runs_land_lane(words) for words in shell_command.step_words(code))
