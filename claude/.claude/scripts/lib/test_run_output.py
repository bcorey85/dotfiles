"""How to read a test runner's output: whether a filtered run reported any passed test."""
import re

from shell_command import parse_piped_commands

TEST_RUNNER = re.compile(r"\b(?:pytest|vitest|jest|mocha|cargo\s+test|go\s+test|bun\s+test"
                         r"|(?:npm|pnpm|yarn|npx)\b.*\btest)\b")
TEST_FILTER = re.compile(r"(?:^|\s)(?:-k|-t|-run|--testNamePattern|--test-name-pattern|--grep|--filter)(?:[\s=]|$)"
                         r"|\S::\w")
CARGO_TEST = re.compile(r"\bcargo\s+(?:\+\S+\s+)?test\b([^;&|]*)")
# The cargo options that take their value as the next token; `--opt=value` carries its own.
CARGO_VALUE_OPTIONS = {"--test", "--bin", "--example", "--bench", "-p", "--package", "--exclude", "--features",
                       "-F", "--target", "--manifest-path", "--profile", "-j", "--jobs", "--target-dir",
                       "--color", "--config", "-Z", "--message-format"}
# `N passed` (pytest, vitest, jest, playwright, cargo), `N passing` (mocha), `N pass` (bun).
PASSED_TESTS = re.compile(r"(\d+) pass(?:ed|ing)?\b")
GO_PACKAGE_OK = re.compile(r"^ok\s+\S+.*$", re.MULTILINE)
# A command substitution `$(...)` or backticks: its runner's output goes into the outer command, not into its report.
SUBSTITUTION = re.compile(r"\$\([^)]*\)|`[^`]*`")
GO_NO_TESTS = "[no tests to run]"


def passed_test_count(output):
    """How many tests the runner output says passed: the sum of every PASSED_TESTS count, plus each go package
    line that ran tests. 0 when the output reports none."""
    total = sum(int(number) for number in PASSED_TESTS.findall(output))
    total += sum(1 for line in GO_PACKAGE_OK.findall(output) if GO_NO_TESTS not in line)
    return total


def cargo_test_is_filtered(command):
    """True when a `cargo test` in the command names a test filter: any token after `--`, or a bare token that is
    not an option or an option's value."""
    for match in CARGO_TEST.finditer(command):
        tokens = match.group(1).split()
        if "--" in tokens[:-1]:
            return True
        skip_value = False
        for token in tokens:
            if skip_value:
                skip_value = False
            elif token == "--":
                break
            elif token in CARGO_VALUE_OPTIONS:
                skip_value = True
            elif not token.startswith("-"):
                return True
    return False


def command_without_piped_stages(command):
    """The command text with each pipeline stage that feeds a later stage left out: the last stage owns the output
    and the exit code, so an earlier stage's report never reaches them. A command that cannot be read as shell
    comes back whole."""
    try:
        commands = parse_piped_commands(command)
    except ValueError:
        return command

    owners = []
    for index, (words, _redirections, _piped) in enumerate(commands):
        feeds_pipe = index + 1 < len(commands) and commands[index + 1][2]
        if not feeds_pipe:
            owners.append(" ".join(words))
    return "\n".join(owners)


def matches_no_test(command, code, output):
    """True for a filtered test run that exits 0 and reports no passed test. A filter that matches nothing exits 0
    in vitest, jest and cargo, so the exit code alone reads it as passing. A runner inside a command substitution
    or piped into another command is not judged: the output does not carry its report."""
    judged = command_without_piped_stages(SUBSTITUTION.sub("", command))
    if code != 0 or not TEST_RUNNER.search(judged):
        return False

    is_filtered = TEST_FILTER.search(judged) or cargo_test_is_filtered(judged)
    if not is_filtered:
        return False
    return passed_test_count(output) == 0
