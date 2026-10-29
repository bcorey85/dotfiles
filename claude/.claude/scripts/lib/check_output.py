"""Reading the output of a check command (a test run, a lint, a full check): whether the environment could not run it,
and which tests failed."""
import pathlib
import re

MAX_FAILING_TEST_LINES = 20

# Exit codes and runner text that mean the check never ran: the shell found no program or could not run it, uv,
# poetry or pipenv could not start one, or the package manager found no package manifest where it ran.
COMMAND_NOT_RUN_CODES = {126, 127}
RUNNER_CANNOT_START = re.compile(r"Failed to spawn: |Command not found: "
                                 r"|the command \S+ could not be found within PATH")
NO_PACKAGE_MANIFEST = re.compile(
    r"ERR_PNPM_NO_IMPORTER_MANIFEST_FOUND|Couldn't find a package\.json"
    r"|ENOENT[^\n]*package\.json|package\.json[^\n]*ENOENT", re.I)
# A package manager that refuses to run here: the project asks for another package-manager or engine version.
PACKAGE_MANAGER_MISMATCH = re.compile(
    r"ERR_PNPM_BAD_PM_VERSION|ERR_PNPM_UNSUPPORTED_ENGINE|npm (?:ERR!|error) code EBADENGINE"
    r"|This project is configured to use|The engine \"node\" is incompatible")
MISSING_MODULE = re.compile(r"No module named '?([A-Za-z_][\w.]*)")
TESTS_FAILED = re.compile(r"\b\d+ failed\b")
# A run that found no test to run: pytest exit 5, vitest and jest exiting non-zero, unittest and Django output.
PYTEST_NO_TESTS_CODE = 5
RAN_NO_TESTS = re.compile(r"No test(?: file)?s found, exiting with code [1-9]|(?i:\bno tests ran\b)"
                          r"|(?m:^Ran 0 tests\b)")
# The line a runner prints for one failed test: pytest `FAILED `/`ERROR ` summary lines, unittest and Django
# `FAIL: `/`ERROR: ` lines, vitest and jest `FAIL ` lines and lines that start with the multiplication sign.
FAILING_TEST_LINE = re.compile(r"^(?:FAILED |ERROR |FAIL: |ERROR: |\s*FAIL\s|\s*\xd7)")
# The text of an elapsed time (`1.5s`, `120 ms`) and of a clock time (`10:20:30`), which the timing patterns share.
ELAPSED_TIME = r"\d+(?:\.\d+)?\s*m?s\b"
CLOCK_TIME = r"\d+:\d{2}:\d{2}"
# A runner's elapsed-time text, which differs between two runs of the same check.
RUNNER_TIMING = re.compile(rf"\({ELAPSED_TIME}\)|\bin {ELAPSED_TIME}(?: \({CLOCK_TIME}\))?")
# A runner's per-run clock line: jest's `Time:`, vitest's `Duration` and `Start at`. The line keeps its label, so it
# still compares, and loses only the time (and vitest's parenthetical) that differs between two runs of the same
# check. A line with any other text after the time keeps all of it.
RUN_CLOCK_LINE = re.compile(
    rf"^\s*(?P<label>Time:|Duration|Start at)\s+(?:{ELAPSED_TIME}|{CLOCK_TIME})(?:\s*\([^)]*\))?\s*$")
# A jest `PASS <file>` line: jest lists the passing files after a failing block, and they are not details of it.
PASSING_FILE_LINE = re.compile(r"^PASS ")
# Where a failing test's name ends and its reason begins: pytest's `FAILED test - reason`.
FAILURE_REASON_SEPARATOR = " - "
# The words of a runner summary count, defined once. NON_FAILURE_WORDS count tests that did not fail, and warnings:
# a diff that adds or removes one changes the count, and it is not a new error. FAILURE_WORDS count failed tests and
# errors.
NON_FAILURE_WORDS = "passed|skipped|total|deselected|warnings?|xfailed|xpassed"
FAILURE_WORDS = "failed|errors?"
# A runner summary count of a non-failure word, with the separator after it.
NON_FAILURE_COUNT = re.compile(rf"\b\d+ (?:{NON_FAILURE_WORDS})\b\s*[,|]?")
# A runner's summary line: only counts (`1 failed, 11 passed in 1.5s`, vitest `Tests  1 failed | 11 passed (12)`, jest
# `Tests: 1 failed, 11 passed, 12 total`), with an optional label and elapsed time. A line with other words, such as
# `expected 3 passed`, is a message.
SUMMARY_COUNT = rf"\d+ (?:{NON_FAILURE_WORDS}|{FAILURE_WORDS})"
# vitest's total test count in parentheses after its summary counts, which changes when a test is added.
SUMMARY_TOTAL = re.compile(r"\(\d+\)")
RUNNER_SUMMARY_LINE = re.compile(
    rf"^[\s=]*(?:(?:Test Files|Tests|Test Suites)\s*:?\s*)?{SUMMARY_COUNT}(?:\s*[,|]\s*{SUMMARY_COUNT})*"
    rf"(?:\s*\(\d+\))?(?:\s+in {ELAPSED_TIME}(?: \({CLOCK_TIME}\))?)?[\s=]*$")
# A Django settings error under pytest, the pytest command that raises it, and the files whose change can raise it
# themselves: a settings module or an app config.
DJANGO_SETTINGS_ERROR = re.compile(r"ImproperlyConfigured|settings are not configured|Apps aren't loaded yet")
PYTEST_COMMAND = re.compile(r"\bpytest\b")
SYNTAX_ERROR = re.compile(r"\bSyntaxError\b")
DJANGO_CONFIG_FILE = re.compile(r"(?:^|/)(?:[^/]*settings[^/]*\.py|apps\.py|settings/[^/]+)$")
# A step that stops on a path that does not exist: git, the shell, `cd`, pytest and python given a script.
MISSING_PATH_LINES = (
    re.compile(r"^fatal: ambiguous argument '(?P<path>.*)': unknown revision or path not in the working tree"),
    re.compile(r"^\S*sh: (?:line \d+: )?(?:cd: )?(?P<path>\S+): No such file or directory"),
    re.compile(r"^\S*sh: \d+: cd: can't cd to (?P<path>\S+)"),
    re.compile(r"^ERROR: file or directory not found: (?P<path>\S+)"),
    re.compile(r"^\S*python[\d.]*: can't open file '(?P<path>[^']+)': \[Errno 2\] No such file or directory"),
)


def is_repo_module(module_name, repo_root):
    top_name = module_name.split(".")[0]
    root = pathlib.Path(repo_root)
    bases = [root, root / "src"]
    return any((base / top_name).is_dir() or (base / f"{top_name}.py").is_file() for base in bases)


def failing_test_lines(output):
    """The lines of the output that name a failed test, without repeats, at most MAX_FAILING_TEST_LINES."""
    names = [line.strip() for line in output.splitlines() if FAILING_TEST_LINE.match(line)]
    return list(dict.fromkeys(names))[:MAX_FAILING_TEST_LINES]


def tail_with_failing_tests(output, tail):
    """The tail of the output with the failing-test lines of the whole output above it, the ones the tail does not
    already hold."""
    missing = [line for line in failing_test_lines(output) if line not in tail]
    if not missing:
        return tail
    return "Failing tests:\n" + "\n".join(missing) + "\n\n" + tail


def normalized_log_line(line):
    """The log line without runner timings (`(5.2 s)`, `in 1.2s`) and, on a runner summary line, without the non-failure
    counts (`10 passed`, `2 skipped`) and vitest's total in parentheses (`(12)`), which differ per run; the failed and
    error counts stay. A per-run clock line (`Time: 1.2 s`) keeps its label and loses its time and, for vitest, the
    parenthetical after it; any other text after the time stays. Any other line keeps its counts: `expected 3 passed`
    in an assertion message is not a runner summary."""
    # A per-run clock line keeps its label and loses only its time, so it compares equal across runs.
    line = RUN_CLOCK_LINE.sub(r"\g<label>", line)
    # A failing test's reason keeps its numbers: `expected 5000ms, got 2000ms` is an assertion, not a timing.
    if FAILING_TEST_LINE.match(line) and FAILURE_REASON_SEPARATOR in line:
        name, separator, reason = line.partition(FAILURE_REASON_SEPARATOR)
        without_timing = RUNNER_TIMING.sub(" ", name) + separator + reason
    else:
        without_timing = RUNNER_TIMING.sub(" ", line)

    without_counts = without_timing
    if RUNNER_SUMMARY_LINE.match(line):
        without_totals = SUMMARY_TOTAL.sub(" ", without_timing)
        without_counts = NON_FAILURE_COUNT.sub(" ", without_totals)
    return " ".join(without_counts.split()).rstrip(",|").rstrip()


def failing_block_details(log_lines):
    """The normalized detail lines of the failing blocks: the non-blank lines after a failing line up to the next
    failing test line or the end of the log. Jest prints one FAIL line per file and a `●` block per test, with blank
    lines between the blocks, so a block runs across its blank lines. A jest `PASS` line is not a detail."""
    details = set()
    in_block = False
    for line in log_lines:
        if FAILING_TEST_LINE.match(line):
            in_block = True
        elif in_block and line.strip() and not PASSING_FILE_LINE.match(line):
            details.add(normalized_log_line(line))
    return details


def missing_path(lines):
    """(line, path) for the first line that says a step stopped on a path that does not exist, else None."""
    for line in lines:
        match = next((match for pattern in MISSING_PATH_LINES if (match := pattern.match(line))), None)
        if match:
            return line.strip(), match.group("path")
    return None


def is_setup_fault(code, output, repo_root, include_missing_modules=True):
    """A failure that says the environment cannot run the check, not that a check failed: the program is missing, the
    runner cannot start it, no package manifest is where it ran, a run found no test to run, a package-manager or
    engine version mismatch, or a module outside the repo is missing and no test ran to a failure. A failed test, a
    missing repo module, a collection error that names no missing module from outside the repo or a name that does
    not import is a real defect. With
    include_missing_modules False, a missing module is always a defect: the change may have added an undeclared
    dependency."""
    if code in COMMAND_NOT_RUN_CODES:
        return True

    if TESTS_FAILED.search(output):
        return False

    if RUNNER_CANNOT_START.search(output) or NO_PACKAGE_MANIFEST.search(output):
        return True

    if PACKAGE_MANAGER_MISMATCH.search(output):
        return True

    ran_no_test = code == PYTEST_NO_TESTS_CODE or RAN_NO_TESTS.search(output)
    if ran_no_test and not failing_test_lines(output):
        return True

    missing_modules = MISSING_MODULE.findall(output)
    if not include_missing_modules or not missing_modules:
        return False
    return not any(is_repo_module(name, repo_root) for name in missing_modules)


def is_django_settings_fault(command, output, changed_file_list):
    """A pytest run that failed on a Django settings error with no failed test: pytest has no Django settings, which
    is not a code defect. A SyntaxError, or a change to a settings module or an app config, which can raise the
    settings error itself, makes it a defect. Under `manage.py test` the settings load first, so a settings error
    there comes from the repo's code."""
    if not PYTEST_COMMAND.search(command) or not DJANGO_SETTINGS_ERROR.search(output):
        return False

    if TESTS_FAILED.search(output) or SYNTAX_ERROR.search(output):
        return False
    return not any(DJANGO_CONFIG_FILE.search(name) for name in changed_file_list)
