"""Read a shell command line as steps joined by operators, without running or fully parsing it."""
import re

SETUP_STEP = re.compile(r"^[ \t(]*(cd[ \t]|source[ \t]|\.[ \t]|export[ \t]|([^\W\d]\w*=[^ \t]*[ \t]*)+$)")
OPERATOR = re.compile(r"(\|\||&&|[|;\n])")


def split_command_steps(command):
    """Split a shell command on ||, &&, | ; and newline into (operator, step) pairs. The operator is the one that
    comes before the step; the first step has "". A newline counts as ";"."""
    pieces = OPERATOR.split(command)
    steps = [("", pieces[0])]
    for index in range(1, len(pieces), 2):
        operator = ";" if pieces[index] == "\n" else pieces[index]
        steps.append((operator, pieces[index + 1]))
    return steps


def step_surely_ran(steps, index, succeeded):
    """True when the step at `index` must have run, given only whether the whole command succeeded. After a
    success every `&&` step ran, but a step behind `||` may have been skipped. After a failure the command stopped
    somewhere unknown, so a step behind `&&` or `||` may never have started, unless every step before that
    operator only sets up the shell (cd, source, export, a bare assignment), which is taken to succeed."""
    skipping = ("||",) if succeeded else ("&&", "||")
    for position in range(index + 1):
        operator = steps[position][0]
        if operator not in skipping:
            continue
        if succeeded or not SETUP_STEP.match(steps[position - 1][1]):
            return False
    return True
