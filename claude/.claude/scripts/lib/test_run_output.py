"""How to read a test runner's output: whether a filtered run reported any passed test."""
import re

TEST_RUNNER = re.compile(r"\b(?:pytest|vitest|jest|mocha|cargo\s+test|go\s+test|bun\s+test"
                         r"|(?:npm|pnpm|yarn|npx)\b.*\btest)\b")
TEST_FILTER = re.compile(r"(?:^|\s)(?:-k|-t|-run|--testNamePattern|--test-name-pattern|--grep|--filter)(?:[\s=]|$)"
                         r"|\S::\w|cargo\s+test\s+(?!-)\S")
# `N passed` (pytest, vitest, jest, playwright, cargo), `N passing` (mocha), `N pass` (bun).
PASSED_TESTS = re.compile(r"(\d+) pass(?:ed|ing)?\b")
GO_PACKAGE_OK = re.compile(r"^ok\s+\S+.*$", re.MULTILINE)
GO_NO_TESTS = "[no tests to run]"


def passed_test_count(output):
    """How many tests the runner output says passed: the sum of every PASSED_TESTS count, plus each go package
    line that ran tests. 0 when the output reports none."""
    total = sum(int(number) for number in PASSED_TESTS.findall(output))
    total += sum(1 for line in GO_PACKAGE_OK.findall(output) if GO_NO_TESTS not in line)
    return total


def matches_no_test(command, code, output):
    """True for a filtered test run that exits 0 and reports no passed test. A filter that matches nothing exits 0
    in vitest, jest and cargo, so the exit code alone reads it as passing."""
    if code != 0 or not TEST_RUNNER.search(command) or not TEST_FILTER.search(command):
        return False
    return passed_test_count(output) == 0
