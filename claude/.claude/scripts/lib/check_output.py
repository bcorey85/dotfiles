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
MISSING_MODULE = re.compile(r"No module named '?([A-Za-z_][\w.]*)")
TESTS_FAILED = re.compile(r"\b\d+ failed\b")
# A run that found no test to run: pytest exit 5, vitest and jest exiting non-zero, unittest and Django output.
PYTEST_NO_TESTS_CODE = 5
RAN_NO_TESTS = re.compile(r"No test(?: file)?s found, exiting with code [1-9]|(?i:\bno tests ran\b)"
                          r"|(?m:^Ran 0 tests\b)")
# The line a runner prints for one failed test: pytest `FAILED `/`ERROR ` summary lines, unittest and Django
# `FAIL: `/`ERROR: ` lines, vitest and jest `FAIL ` lines and lines that start with the multiplication sign.
FAILING_TEST_LINE = re.compile(r"^(?:FAILED |ERROR |FAIL: |ERROR: |\s*FAIL\s|\s*\xd7)")
# A Django settings error under pytest, the pytest command that raises it, and the files whose change can raise it
# themselves: a settings module or an app config.
DJANGO_SETTINGS_ERROR = re.compile(r"ImproperlyConfigured|settings are not configured|Apps aren't loaded yet")
PYTEST_COMMAND = re.compile(r"\bpytest\b")
SYNTAX_ERROR = re.compile(r"\bSyntaxError\b")
DJANGO_CONFIG_FILE = re.compile(r"(?:^|/)(?:[^/]*settings[^/]*\.py|apps\.py|settings/[^/]+)$")


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


def is_setup_fault(code, output, repo_root, include_missing_modules=True):
    """A failure that says the environment cannot run the check, not that a check failed: the program is missing, the
    runner cannot start it, no package manifest is where it ran, a run found no test to run, or a module outside the
    repo is missing and no test ran to a failure. A failed test, a missing repo module, a collection error that names
    no missing module from outside the repo or a name that does not import is a real defect. With
    include_missing_modules False, a missing module is always a defect: the change may have added an undeclared
    dependency."""
    if code in COMMAND_NOT_RUN_CODES:
        return True

    if TESTS_FAILED.search(output):
        return False

    if RUNNER_CANNOT_START.search(output) or NO_PACKAGE_MANIFEST.search(output):
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
