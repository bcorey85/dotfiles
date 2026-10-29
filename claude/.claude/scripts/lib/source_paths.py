"""Which file paths count as source: not a test, a lockfile or a generated file."""

LOCKFILE_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock", "Cargo.lock",
                  "Gemfile.lock", "composer.lock", "go.sum", "bun.lockb"}
SCRIPT_SUFFIXES = (".ts", ".tsx", ".mts", ".js", ".jsx", ".mjs")


def is_test_path(path):
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    parts = lowered.split("/")[:-1]
    return any(part in ("test", "tests", "__tests__", "spec", "specs") for part in parts) or is_test_name(name)


def is_test_name(name):
    return (name.startswith("test_") or ".test." in name or ".spec." in name or "_test." in name
            or name in ("test.py", "tests.py"))


def is_runnable_test_file(path, counts_jest_tests_folder=False):
    # A file a test runner can take as a target: test-named, or, for jest, which runs every script file under
    # __tests__/ by default, such a file. Support files under tests/ (__init__.py, conftest.py, factories) are not.
    # The test_ prefix, _test. infix and test.py/tests.py names are Python conventions; .test. and .spec. hold for
    # every language.
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    if ".test." in name or ".spec." in name:
        return True

    if name.endswith(".py") and is_test_name(name):
        return True

    if not counts_jest_tests_folder:
        return False

    parts = path.split("/")[:-1]
    return "__tests__" in parts and name.endswith(SCRIPT_SUFFIXES)


def is_uncounted_path(path):
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    return (path.rsplit("/", 1)[-1] in LOCKFILE_NAMES or name.endswith(".lock") or "__snapshots__" in lowered
            or name.endswith(".snap") or "generated" in lowered or ".generated." in name or ".gen." in name
            or name.endswith(".min.js") or "dist" in lowered.split("/")[:-1])


def is_counted_source(path):
    return not is_test_path(path) and not is_uncounted_path(path)
