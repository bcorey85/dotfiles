"""How to tell whether a command runs tests, and how to read a test runner's output: whether a filtered run
reported any passed test."""
import pathlib
import re

from shell_command import parse_piped_commands, split_simple_commands, without_assignments

TEST_RUNNER_WORDS = ("pytest", "vitest", "jest", "mocha")
TEST_RUNNER = re.compile(r"\b(?:" + "|".join(TEST_RUNNER_WORDS) + r"|cargo\s+test|go\s+test|bun\s+test"
                         r"|(?:npm|pnpm|yarn|npx)\b.*\btest)\b")
TEST_FILTER = re.compile(r"(?:^|\s)(?:-k|-t|-run|--testNamePattern|--test-name-pattern|--grep|--filter)(?:[\s=]|$)"
                         r"|\S::\w")
CARGO_TEST = re.compile(r"\bcargo\s+(?:\+\S+\s+)?test\b([^;&|]*)")
# The cargo options that take their value as the next token; `--opt=value` carries its own.
CARGO_VALUE_OPTIONS = {"--test", "--bin", "--example", "--bench", "-p", "--package", "--exclude", "--features",
                       "-F", "--target", "--manifest-path", "--profile", "-j", "--jobs", "--target-dir",
                       "--color", "--config", "-Z", "--message-format"}
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
TEST_WORD = re.compile(r"^test(?:[:-][\w:.-]*)?$")
# Programs that run a named script or target, and Django's `manage.py`: a `test` word given to one runs tests.
SCRIPT_RUNNERS = ("npm", "pnpm", "yarn", "bun", "make", "just", "task", "cargo", "go", "deno", "manage.py")
# Programs whose arguments only name a test: a search, a file check, a print, a directory change.
NON_TEST_PROGRAMS = ("test", "cd", "git", "rg", "grep", "echo", "cat", "ls", "find", "diff")


def runs_tests(command):
    """True when a step of the shell command runs tests: a word that is `pytest`, `vitest`, `jest` or `mocha`, or
    `test` or a script or target name that starts `test:` or `test-`, given to a script runner (`npm test`,
    `make test-unit`, `pnpm --filter api test`, `python manage.py test`). A search, a file check, a `cd` or a tool
    whose argument merely names a test folder is not. False for text shlex cannot split."""
    try:
        simple_commands = split_simple_commands(command)
    except ValueError:
        return False

    for words in simple_commands:
        words = without_assignments(words)
        if not words or words[0] in NON_TEST_PROGRAMS:
            continue

        if any(word in TEST_RUNNER_WORDS for word in words):
            return True

        runner_seen = False
        for word in words:
            if runner_seen and TEST_WORD.match(word):
                return True
            if pathlib.PurePosixPath(word).name in SCRIPT_RUNNERS:
                runner_seen = True
    return False


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
