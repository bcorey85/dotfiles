"""Read a shell command line as steps joined by operators, without running or fully parsing it."""
import re

SETUP_STEP = re.compile(r"^[ \t(]*(cd[ \t]|source[ \t]|\.[ \t]|export[ \t]|([^\W\d]\w*=[^ \t]*[ \t]*)+$)")
# `|&` (pipe both streams), `>&`, `&>` and `&&` are not a lone `&`; a lone `&` sends the step before it to the background.
OPERATOR = re.compile(r"(\|\||&&|\|(?!&)|(?<![>&|])&(?![&>])|;|\n)")
LEADING_BRACES = re.compile(r"(?:[ \t]*\{(?=[ \t]))*")
TRAILING_BRACES = re.compile(r"(?:(?:^|[ \t])\}[ \t]*)+$")


def split_command_steps(command):
    """Split a shell command on ||, &&, | ; newline and a lone & into (operator, step) pairs. The operator is the one
    that comes before the step; the first step has "". A newline counts as ";"."""
    pieces = OPERATOR.split(command)
    steps = [("", pieces[0])]
    for index in range(1, len(pieces), 2):
        operator = ";" if pieces[index] == "\n" else pieces[index]
        steps.append((operator, pieces[index + 1]))
    return steps


def group_depth_change(step):
    """How many `( ... )` and `{ ...; }` groups the step text opens, minus how many it closes."""
    change = step.count("(") - step.count(")")
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
