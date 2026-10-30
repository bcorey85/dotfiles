"""Which file paths count as source: not a test, a lockfile or a generated file. The one owner of the two test-file
rules every gate reads: `is_test_path` (the file belongs to the tests) and `is_runnable_test_file` (a test runner
can take it alone as a target)."""

LOCKFILE_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock", "Cargo.lock",
                  "Gemfile.lock", "composer.lock", "go.sum", "bun.lockb"}
SCRIPT_SUFFIXES = (".ts", ".tsx", ".mts", ".js", ".jsx", ".mjs")


def is_test_path(path):
    """Whether the file belongs to the tests: test-named, or anywhere under a test folder, support files
    (conftest.py, factories, fixtures) included. It never counts toward source size. A file can be a test file and
    still not run alone; see `is_runnable_test_file`."""
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    parts = lowered.split("/")[:-1]
    return any(part in ("test", "tests", "__tests__", "spec", "specs") for part in parts) or is_test_name(name)


def is_test_name(name):
    return (name.startswith("test_") or ".test." in name or is_spec_name(name) or "_test." in name
            or name in ("test.py", "tests.py"))


def is_spec_name(name):
    return ".spec." in name.lower()


def names_spec_file(text):
    """Whether any word of the text, such as a failing check's log tail, names a spec file."""
    return any(is_spec_name(word.rsplit("/", 1)[-1]) for word in text.split())


def is_runnable_test_file(path, counts_jest_tests_folder=False, discovers_django_tests=False):
    """Whether a test runner can take the file alone as a target: test-named, or, for jest, which runs every script
    file under __tests__/ by default, such a file. Support files under tests/ (__init__.py, conftest.py, factories)
    are test files but do not run alone. The test_ prefix, _test. infix and test.py/tests.py names are Python
    conventions; .test. and .spec. hold for every language. `manage.py test` finds only modules that match its
    default pattern, test*.py."""
    name = path.rsplit("/", 1)[-1]
    if discovers_django_tests:
        return name.startswith("test") and name.endswith(".py")

    lowered_name = name.lower()
    if ".test." in lowered_name or is_spec_name(lowered_name):
        return True

    if lowered_name.endswith(".py") and is_test_name(lowered_name):
        return True

    if not counts_jest_tests_folder:
        return False

    parts = path.split("/")[:-1]
    return "__tests__" in parts and lowered_name.endswith(SCRIPT_SUFFIXES)


def is_uncounted_path(path):
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    return (path.rsplit("/", 1)[-1] in LOCKFILE_NAMES or name.endswith(".lock") or "__snapshots__" in lowered
            or name.endswith(".snap") or "generated" in lowered or ".generated." in name or ".gen." in name
            or name.endswith(".min.js") or "dist" in lowered.split("/")[:-1])


def is_counted_source(path):
    return not is_test_path(path) and not is_uncounted_path(path)


# A change that adds this many lines to files that count toward size (`counts_toward_size`) is large: it gets the
# structure pass.
LARGE_ADDED_LINES = 40


def counts_toward_size(path):
    """Whether a changed file's added lines count toward the LARGE_ADDED_LINES bar: counted source, and not a doc."""
    return is_counted_source(path) and not path.endswith(".md")


def is_large_change(added_lines, new_paths):
    """Whether a change is large: it adds LARGE_ADDED_LINES lines to files that count toward size, or it creates a
    new counted source file (untracked or added to the index)."""
    return added_lines >= LARGE_ADDED_LINES or any(is_counted_source(path) for path in new_paths)
