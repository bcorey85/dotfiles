"""How to read a test runner's output: the runner's summary lines, the passed-test count, and whether a filtered run
reported any passed test. Whether a command runs tests is check_scope's."""
import re

from check_scope import names_test_filter, names_test_runner, runs_tests
from shell_command import parse_piped_commands

# `N passed` (pytest, vitest, jest, playwright, cargo), `N passing` (mocha), `N pass` (bun).
PASSED_TESTS = re.compile(r"([1-9]\d*) pass(?:ed|ing)?\b")
GO_PACKAGE_OK = re.compile(r"^ok[ \t]+\S+\t(?:[\d.]+s|\(cached\)).*$", re.MULTILINE)
MAX_RUNNER_SUMMARIES = 5
# The mark node --test's spec reporter prints in front of a summary line.
INFO_MARK = "\N{INFORMATION SOURCE}"
# The one-line summaries: pytest (with or without the `=` bars), vitest, jest, mocha, cargo, bun, playwright,
# node --test and the dotfiles suite runner.
SUMMARY_LINES = (
    re.compile(r"^=+ .*\b\d+ (?:passed|failed|errors?)\b.* in [\d.:]+s.*=+$", re.MULTILINE),
    re.compile(r"^\d+ (?:passed|failed|errors?)\b.* in [\d.:]+s\b.*$", re.MULTILINE),
    re.compile(r"^[ \t]*Tests {2,}[1-9]\d* (?:passed|failed).*$", re.MULTILINE),
    re.compile(r"^Tests:\s.*\btotal\b.*$", re.MULTILINE),
    re.compile(r"^[ \t]*[1-9]\d* passing\b.*$", re.MULTILINE),
    re.compile(r"^test result: (?:FAILED\. |\w+\. (?=[1-9]))\d+ passed.*$", re.MULTILINE),
    re.compile(r"^[ \t]*[1-9]\d* pass$", re.MULTILINE),
    re.compile(r"^[ \t]*[1-9]\d* (?:passed|failed)\b.*\([\d.]+m?s\)$", re.MULTILINE),
    re.compile(rf"^(?:#|{INFO_MARK}) pass [1-9]\d*$", re.MULTILINE),
    # The dotfiles suite runner's total: `N tests in M files, wall-clock ..., K failed`.
    re.compile(r"^[1-9]\d* tests in \d+ files, .*\b\d+ failed$", re.MULTILINE),
    # The failure counts, kept only above zero: mocha, bun, node --test, playwright and go.
    re.compile(r"^[ \t]*[1-9]\d* failing\b.*$", re.MULTILINE),
    re.compile(r"^[ \t]*[1-9]\d* fail$", re.MULTILINE),
    re.compile(rf"^(?:#|{INFO_MARK}) fail [1-9]\d*$", re.MULTILINE),
    re.compile(r"^[ \t]*[1-9]\d* failed$", re.MULTILINE),
    re.compile(r"^FAIL\t\S+.*$", re.MULTILINE),
)
# unittest and Django: `Ran N tests in Xs`, then `OK` or `FAILED (...)` on a later line.
UNITTEST_SUMMARY = re.compile(r"^(Ran [1-9]\d* tests? in [\d.]+s)\s*\n+\s*(OK\b[^\n]*|FAILED\b[^\n]*)", re.MULTILINE)
# A command substitution `$(...)` or backticks: its runner's output goes into the outer command, not into its report.
SUBSTITUTION = re.compile(r"\$\([^)]*\)|`[^`]*`")
GO_NO_TESTS = "[no tests to run]"


def passed_test_count(output):
    """How many tests the runner output says passed: the sum of every PASSED_TESTS count, plus each go package
    line that ran tests. 0 when the output reports none."""
    total = sum(int(number) for number in PASSED_TESTS.findall(output))
    total += sum(1 for line in GO_PACKAGE_OK.findall(output) if GO_NO_TESTS not in line)
    return total


def runner_summaries(output, limit=MAX_RUNNER_SUMMARIES):
    """The runner's own summary lines in the output, in the order printed, without repeats, at most
    `limit` (None for all): pytest, unittest and Django, vitest, jest, mocha, cargo, bun, playwright, node --test,
    go and the dotfiles suite runner. A chained command prints one per runner. Go's package lines count as one
    summary. Empty when the output holds none."""
    found = []
    for pattern in SUMMARY_LINES:
        found += [(match.start(), match.group(0).strip(" =\t")) for match in pattern.finditer(output)]

    for match in UNITTEST_SUMMARY.finditer(output):
        found.append((match.start(), f"{match.group(1)}: {match.group(2)}"))

    go_packages = [match for match in GO_PACKAGE_OK.finditer(output) if GO_NO_TESTS not in match.group(0)]
    if go_packages:
        found.append((go_packages[0].start(), f"go: {len(go_packages)} packages ok"))

    ordered = [text for _position, text in sorted(found)]
    return list(dict.fromkeys(ordered))[:limit]


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
    names_runner = names_test_runner(judged) or runs_tests(judged)
    if code != 0 or not names_runner:
        return False

    if not names_test_filter(judged):
        return False
    return passed_test_count(output) == 0
