"""Read the steps of a split command line (the `(operator, text)` pairs of `split_command_steps`): which step may be
skipped, runs in the background or surely ran, where `( )` and `{ }` groups open and close, and which folder each simple
command runs in (`placed_commands`)."""
import re
import sys
from typing import NamedTuple

from shell_command import command_after_wrappers, split_command_steps, split_simple_commands
from shell_directory import CD_WORD, DIRECTORY_MOVE_WORDS, ShellDirectory
from shell_quoting import quoted_positions

# A step after an operator and a newline keeps that newline at its start.
SETUP_STEP = re.compile(rf"^[ \t\n(]*({CD_WORD}[ \t]|source[ \t]|\.[ \t]|export[ \t]|([^\W\d]\w*=[^ \t]*[ \t]*)+$)")
LEADING_BRACES = re.compile(r"(?:[ \t\n]*\{(?=[ \t\n]|$))*")
TRAILING_BRACES = re.compile(r"(?:(?:^|[ \t\n])\}[ \t]*)+$")
# The characters that may come before a step's command word: blanks, the newline a step keeps after an operator, and
# the openers of groups.
STEP_OPENERS = " \t\n({"
DIRECTORY_MOVE_IN_TEXT = re.compile(rf"(?<![^\s;&|(])(?:{'|'.join(DIRECTORY_MOVE_WORDS)})(?![^\s;&|)])")


def group_closes(step):
    """(opened, closed): how many `(` the step opens before its first command, and how many `)` it closes beyond the
    ones its own text opens after that. A parenthesis in quotes is no group."""
    quoted = quoted_positions(step, unclosed_is_quoted=False)
    opened = step[:len(step) - len(step.lstrip(STEP_OPENERS))].count("(")
    unquoted_opens = sum(1 for index, char in enumerate(step) if char == "(" and index not in quoted)
    unquoted_closes = sum(1 for index, char in enumerate(step) if char == ")" and index not in quoted)
    return opened, max(0, unquoted_closes - (unquoted_opens - opened))


def step_parts(step):
    """(core, tail) of a step: the command text after the `(` groups it opens, up to the first `)` that closes no `(`
    of its own, and the text after the last such `)` (a redirection or pipe that applies to the closed group). A
    quoted parenthesis is part of the command."""
    quoted = quoted_positions(step, unclosed_is_quoted=False)
    start = 0
    while start < len(step) and step[start] in STEP_OPENERS and start not in quoted:
        start += 1
    depth = 0
    closing = []
    for index in range(start, len(step)):
        if index in quoted:
            continue
        if step[index] == "(":
            depth += 1
            continue
        if step[index] != ")":
            continue
        if depth:
            depth -= 1
            continue
        closing.append(index)
    if not closing:
        return step[start:], ""
    return step[start:closing[0]], step[closing[-1] + 1:]


def paren_depth_change(step):
    """How many `( ... )` subshells the step text opens, minus how many it closes. A quoted parenthesis counts for
    nothing."""
    quoted = quoted_positions(step, unclosed_is_quoted=False)
    unquoted = [char for index, char in enumerate(step) if index not in quoted]
    return unquoted.count("(") - unquoted.count(")")


def closes_brace_group(step):
    """True when the step ends in a `}` that closes a `{ ...; }` group."""
    return TRAILING_BRACES.search(step) is not None


def group_depth_change(step):
    """How many `( ... )` and `{ ...; }` groups the step text opens, minus how many it closes. A quoted parenthesis
    opens and closes nothing."""
    change = paren_depth_change(step)
    change += LEADING_BRACES.match(step).group().count("{")
    trailing = TRAILING_BRACES.search(step)
    return change - (trailing.group().count("}") if trailing else 0)


def step_may_be_skipped(steps, index):
    """True when an `||` before the step, in the same list (after the last `;`, newline or `&`), can skip it."""
    for position in range(index, 0, -1):
        operator = steps[position][0]
        if operator in (";", "&"):
            return False
        if operator == "||":
            return True
    return False


def runs_only_after_success(steps, earlier, later):
    """True when the step at `later` comes after the step at `earlier`, which itself is not skipped by an `||`, and
    runs only if `earlier` succeeded. The step right after `earlier` must be joined by `&&`; after that `&&` and `|`
    keep the chain (a pipe binds tighter than `&&`). A `;`, newline, `||` or `&` ends it, except inside a `( )` or
    `{ }` group that the chain entered. Limit: a group closed and another one opened in one step is not tracked."""
    if later <= earlier or step_may_be_skipped(steps, earlier):
        return False
    depth = 0
    for position in range(earlier + 1, later + 1):
        operator = steps[position][0]
        if position == earlier + 1 and operator != "&&":
            return False
        if depth == 0 and operator not in ("&&", "|"):
            return False
        depth = max(0, depth + group_depth_change(steps[position][1]))
    return True


def step_runs_in_background(steps, index):
    """True when the `&&`/`||`/`|` list holding the step at `index` is ended by a lone `&`: bash runs that whole
    list in the background."""
    for position in range(index + 1, len(steps)):
        operator = steps[position][0]
        if operator not in ("|", "&&", "||"):
            return operator == "&"
    return False


def step_surely_ran(steps, index, succeeded):
    """True when the step at `index` must have run, given only whether the whole command succeeded. After a
    success every `&&` step ran, but a step behind `||` may have been skipped. After a failure the command stopped
    somewhere unknown, so a step behind `&&` or `||` may never have started, unless every step before that
    operator only sets up the shell (cd, source, export, a bare assignment), which is taken to succeed. A step sent
    to the background with `&` never counts: the command's result says nothing about it."""
    if step_runs_in_background(steps, index):
        return False
    skipping = ("||",) if succeeded else ("&&", "||")
    for position in range(index + 1):
        operator = steps[position][0]
        if operator not in skipping:
            continue
        if succeeded or not SETUP_STEP.match(steps[position - 1][1]):
            return False
    return True


class PlacedCommand(NamedTuple):
    step: str
    simple_command: list
    words: list
    directory: str | None


def placed_commands(command, start_dir, peel_containers=True, skip_unread=False):
    """Each simple command of `command` that is not a `cd`, `pushd` or `popd`, as a PlacedCommand: its step, its words,
    its words after the wrappers, and `directory`, where the shell stands when it runs (`start_dir` moved by the
    earlier moves; a `cd` inside `( ... )` ends where the group closes; a `$( ... )` inside a step is no group).
    Raises ValueError for a step that split_simple_commands cannot read. With `skip_unread`, such a step is reported
    on stderr and left out, and the reading goes on; when it holds a `cd`, `pushd` or `popd` word, the folder of the
    later commands is unknown (None) until the enclosing group closes."""
    shell = ShellDirectory(start_dir)
    outer_shells = []
    for _operator, step in split_command_steps(command):
        opened, closed = group_closes(step)
        outer_shells.extend([shell.saved()] * opened)
        try:
            simple_commands = split_simple_commands(step)
        except ValueError as error:
            if not skip_unread:
                raise
            sys.stderr.write(f"shell_steps: step not read ({error}): {step!r}\n")
            if DIRECTORY_MOVE_IN_TEXT.search(step):
                shell.current = None
            simple_commands = []
        for simple_command in simple_commands:
            words = command_after_wrappers(simple_command, peel_containers=peel_containers)
            if not words:
                continue
            if words[0] in DIRECTORY_MOVE_WORDS:
                shell.apply(words)
                continue
            yield PlacedCommand(step, simple_command, words, shell.current)
        for _group in range(min(closed, len(outer_shells))):
            shell.restore(outer_shells.pop())
