"""The one owner of every question about a shell command line. It says whether the command runs tests (runs_tests,
names_test_runner), whether a step can print a runner summary of its own (prints_own_runner_summary), which runner
families it runs (runner_family), whether it is a test, lint, typecheck or build run (is_check), whether it names a
test filter (names_test_filter) or a cargo test target (names_cargo_test_target), and how wide a check it runs: a
whole test suite, lint or build, a targeted run, or none (command_check_scope). A whole run of a runner in
RUNNER_VALUE_FLAGS reads none, not whole. A make target or a docker exec or run call is judged by the commands it
runs (make is read from the Makefile text; a NAME=value argument, a missing Makefile or a missing target makes the
coder gate and a full-check receipt let the call through, and make -n, -q, -t or -h runs no
recipe line except one marked `+` or one that names `$(MAKE)`, which is not judged). Runner wrappers (poetry,
pipenv or uv run, env, timeout and the like) are peeled first, so the command they run is the one judged."""
import os
import pathlib
import re
import shlex

from makefile_text import load_makefile, parse_make_arguments
from pytest_config import pytest_options
from shell_command import (
    and_steps_or_whole,
    command_after_wrappers,
    contains_word_run,
    docker_forwarded_variables,
    docker_set_variables,
    resolved_command_words,
    split_command_steps,
    split_simple_commands,
    step_words,
    unwrap_docker,
    without_assignments,
    without_flag_values,
)

PYTHON_PROGRAM = re.compile(r"python(3(\.\d+)?)?")
# `manage.py test` options that take the next word as their value, which is not a test label.
MANAGE_TEST_VALUE_OPTIONS = {
    "-v", "--verbosity", "--settings", "--pythonpath", "--parallel", "--testrunner", "-t", "--top-level-directory",
    "-p", "--pattern", "--tag", "--exclude-tag",
}
# By runner: the flags that leave files or tests out of a `manage.py test` or CHECK_RUN_PREFIXES run. For the
# CHECK_RUN_PREFIXES runners their space form already reads its value as a scope word; this list reads the `=` form.
# ruff's --ignore takes rule codes, so it is no leave-out flag there. A script run through npm, yarn, pnpm or bun reads
# the flags of every runner but ruff.
LEAVES_OUT_FLAGS = {
    "manage.py": {"--exclude-tag"},
    "pytest": {"--ignore", "--ignore-glob", "--deselect", "--lf", "--last-failed", "--sw", "--stepwise", "--co",
               "--collect-only"},
    "vitest": {"--exclude"},
    "jest": {"--testPathIgnorePatterns"},
    "eslint": {"--ignore-pattern", "--ignore-path"},
    "ruff": {"--exclude", "--extend-exclude"},
}
# The leave-out flags read for every CHECK_RUN_PREFIXES run but `ruff check`.
NON_RUFF_LEAVE_OUT_FLAG_SETS = [flags for runner, flags in LEAVES_OUT_FLAGS.items() if runner != "ruff"]
CHECK_RUN_LEAVES_OUT_FLAGS = set().union(*NON_RUFF_LEAVE_OUT_FLAG_SETS)

# The command starts of a test or lint run. A simple command that starts with one covers the whole package when no
# path, test name, changed-files flag or exclude flag follows it. The words "test" and "lint" in a prefix also match
# script names such as "test:unit". A test root folder after a lint start (`ruff check tests`) is a path that limits
# the run, so it counts as scope.
CHECK_RUN_PREFIXES = [
    ["npm", "test"], ["npm", "t"], ["npm", "run", "test"], ["yarn", "test"], ["yarn", "run", "test"],
    ["pnpm", "test"], ["pnpm", "run", "test"], ["bun", "test"], ["npx", "vitest"], ["npx", "jest"],
    ["vitest"], ["jest"], ["pytest"], ["python", "-m", "pytest"],
    ["npm", "run", "lint"], ["yarn", "lint"], ["yarn", "run", "lint"], ["pnpm", "lint"], ["pnpm", "run", "lint"],
    ["npx", "eslint"], ["eslint"], ["ruff", "check"],
]
# These are the only prefixes after which naming a test root folder is no scope.
PYTEST_RUN_PREFIXES = [["pytest"], ["python", "-m", "pytest"]]
UNITTEST_PREFIX = ["python", "-m", "unittest"]
UNITTEST_SELECTION_FLAGS = ("-k", "-p", "--pattern")
# `unittest discover` options that take the next word as their value, which is not a start directory or pattern.
DISCOVER_VALUE_OPTIONS = {"-s", "-t", "--start-directory", "--top-level-directory"}
# The words that make any step a unittest run, wherever the step puts them.
UNITTEST_MODULE_WORDS = ["-m", "unittest"]
# A build always covers the whole package.
BUILD_PREFIXES = [
    ["npm", "run", "build"], ["yarn", "build"], ["yarn", "run", "build"], ["pnpm", "build"], ["pnpm", "run", "build"],
    ["bun", "run", "build"],
]
# Runners read by their own flags, not by CHECK_RUN_PREFIXES. One runs on part of its suite when given a positional
# word (a file, a directory, a package or a test name) or a selector flag. By runner: the flags that take a value
# word, which is no scope. tsc's and dotnet's project flags name the build file, and a whole run with them reads none.
RUNNER_VALUE_FLAGS = {
    "cargo": {"--manifest-path", "--target-dir", "--target", "-j", "--jobs", "--features", "-F", "--profile", "-D",
              "-A", "-W", "--test-threads", "--color", "--message-format", "--config", "-Z", "--retries",
              "--failure-output", "--success-output", "--status-level", "--final-status-level",
              "--max-fail", "--cargo-profile", "--archive-file", "--format", "--logfile", "-P", "--run-ignored"},
    "go": {"-p", "-coverprofile", "-o", "-count", "-timeout", "-parallel", "-tags", "-cpu", "-covermode",
           "-shuffle", "-mod", "-vet", "-gcflags", "-ldflags", "-asmflags", "-exec", "-modfile", "-overlay",
           "-coverpkg", "-bench", "-benchtime", "-blockprofile", "-blockprofilerate", "-cpuprofile", "-memprofile",
           "-memprofilerate", "-mutexprofile", "-mutexprofilefraction", "-trace", "-outputdir", "-testlogfile",
           "-fuzztime", "-fuzzminimizetime", "-pgo", "-buildmode", "-buildvcs", "-toolexec", "-compiler",
           "-installsuffix", "-list"},
    "mypy": {"--python-version", "--config-file", "--cache-dir", "--python-executable", "--platform",
             "--follow-imports", "--disable-error-code", "--enable-error-code", "--junit-xml", "--html-report",
             "--cobertura-xml-report", "--linecount-report", "--custom-typeshed-dir", "--always-true"},
    "pyright": {"-p", "--project", "--pythonversion", "--pythonpath", "--venvpath", "--level", "--typeshedpath",
                "--pythonplatform", "--createstub", "--verifytypes"},
    "tsc": {"-p", "--project", "-t", "--target", "-m", "--module", "--outDir", "--lib"},
    "dotnet": {"--project", "-c", "--configuration", "-f", "--framework", "--logger", "-v", "--verbosity", "-r",
               "--runtime", "-o", "--output", "--settings", "--collect", "-s", "--arch", "-a", "--os",
               "--test-adapter-path", "--diag", "--results-directory", "-e", "--environment",
               "--blame-hang-timeout"},
    # bats' -p is --pretty, a switch that takes no value and names no tests.
    "bats": {"-j", "--jobs", "-F", "--formatter", "-o", "--output", "--report-formatter"},
    "rspec": {"-f", "--format", "-r", "--require", "-I", "--seed", "--order", "--out", "--default-path",
              "--failure-exit-code", "--deprecation-out", "-O", "--options"},
    "phpunit": {"-c", "--configuration", "--log-junit", "--bootstrap", "-d", "--coverage-clover",
                "--coverage-html", "--coverage-xml", "--testdox-html", "--cache-result-file", "--order-by",
                "--random-order-seed", "--printer", "--test-suffix", "--extensions", "--cache-directory",
                "--processes", "--log-tap"},
}
# By runner: the flags that pick part of the suite, or leave part of it out, and take a value, as `--flag value` or
# `--flag=value`.
RUNNER_SELECTOR_VALUE_FLAGS = {
    "cargo": {"-p", "--package", "--test", "--bench", "--bin", "--example", "-E", "--filterset", "--filter-expr",
              "--skip", "--partition", "--exclude"},
    "go": {"-run", "-skip", "-fuzz"},
    "mypy": {"-p", "--package", "-m", "--module", "--exclude"},
    "dotnet": {"--filter"},
    "rspec": {"-e", "--example", "-t", "--tag", "-P", "--pattern", "--exclude-pattern"},
    "phpunit": {"--filter", "--testsuite", "--group", "--exclude-group", "--exclude-filter", "--exclude-testsuite"},
    "bats": {"--filter", "-f", "--filter-tags", "--negative-filter"},
}
# By runner: the switches that pick part of the suite.
RUNNER_SELECTOR_SWITCHES = {
    "cargo": {"--lib", "--doc", "--bins", "--tests", "--benches", "--examples",
              "--ignored"},
    "rspec": {"--only-failures", "--next-failure"},
}
# nextest's --run-ignored runs only the ignored tests with one of these values; `all` and `default` stay whole.
NEXTEST_IGNORED_ONLY_VALUES = {"only", "ignored-only"}
# These runners take a subcommand first (cargo test, go vet, cargo nextest run), which is no scope.
SUBCOMMAND_RUNNERS = ("cargo", "go", "dotnet")
NEXTEST_SUBCOMMAND = ["nextest", "run"]
RUNNER_LAUNCHERS = (["npx"], ["bunx"], ["bundle", "exec"])
WHOLE_GO_MODULE = "./..."
SCRIPT_VARIANT_WORDS = ("test", "lint", "build")
SCOPE_RANK = {"none": 0, "targeted": 1, "unresolved": 2, "whole": 3}
MAKE_PROGRAMS = ("make", "gmake")
MAX_MAKE_DEPTH = 5
CHANGED_FILES_FLAGS = ("--changed", "--onlyChanged")
WHOLE_PACKAGE_PATHS = {".", "./"}

# What runs tests. A word that is one of these runs tests wherever it stands in a step.
TEST_RUNNER_WORDS = ("pytest", "vitest", "jest", "mocha")
# The wide text reading of a test runner: a runner word, `cargo test`, `go test`, `bun test`, or a package manager
# with a `test` word anywhere after it. A search or print step that names a runner matches it too.
TEST_RUNNER = re.compile(r"\b(?:" + "|".join(TEST_RUNNER_WORDS) + r"|cargo\s+test|go\s+test|bun\s+test"
                         r"|(?:npm|pnpm|yarn|npx)\b.*\btest\b)\b")
# The flags that select tests by name or path and take a value.
SELECTION_VALUE_FLAGS = ("-k", "-m", "-t", "-run", "--testNamePattern", "--test-name-pattern", "--testPathPattern",
                         "--grep", "--filter")
# A command-line flag that names which tests to run. `-m` is left out: `python -m pytest` is no filter.
TEST_FILTER_FLAGS = [flag for flag in SELECTION_VALUE_FLAGS if flag != "-m"] + ["--skip"]
TEST_FILTER = re.compile(r"(?:^|\s)(?:" + "|".join(re.escape(flag) for flag in TEST_FILTER_FLAGS)
                         + r")(?:[\s=]|$)|\S::\w")
TEST_WORD = re.compile(r"^(?:test(?:[:-][\w:.-]*)?|nextest)$")
# Programs that run a named script or target, and Django's `manage.py`: a `test` word given to one runs tests.
SCRIPT_RUNNERS = ("npm", "pnpm", "yarn", "bun", "make", "just", "task", "cargo", "go", "deno", "manage.py")
# Programs whose arguments only name a test: a search, a file check, a print, a directory change.
NON_TEST_PROGRAMS = ("test", "cd", "git", "rg", "grep", "echo", "cat", "ls", "find", "diff",
                     "head", "tail", "sed", "less", "more", "tac", "nl", "awk", "cut", "sort", "uniq", "wc", "jq",
                     "strings", "bat")
DJANGO_TEST_RUN = re.compile(r"\bmanage\.py\s+test\b")
# The runner families a test command can run, read from its text.
RUNNER_FAMILY_PATTERNS = {
    "js": re.compile(r"\b(?:vitest|jest|mocha)\b|\b(?:npm|pnpm|yarn|bun|npx)\b.*\btest\b"),
    "python": re.compile(rf"\bpytest\b|{DJANGO_TEST_RUN.pattern}"),
    "cargo": re.compile(r"\bcargo\s+(?:test|nextest)\b"),
}

# What is a check: a test, lint, typecheck or build run. A program here is a check with any arguments.
CHECK_PROGRAMS = {"tsc", "eslint", "ruff", "mypy", "golangci-lint", "rspec", "phpunit", "shellcheck", "luacheck",
                  "stylua", "bats", "pyright", *TEST_RUNNER_WORDS}
# By program: the subcommands that make it a check.
CHECK_SUBCOMMANDS = {
    "go": {"test", "vet"}, "cargo": {"test", "nextest", "clippy", "check"}, "dotnet": {"test"}, "mvn": {"test"},
    "gradle": {"test"}, "make": {"test", "lint", "check", "typecheck"},
}
PACKAGE_SCRIPT_RUNNERS = {"npm", "pnpm", "yarn", "bun"}
# Package-manager verbs that add, remove or change a package: a test word after one names a package.
PACKAGE_VERBS = {"install", "i", "ci", "add", "remove", "uninstall", "rm", "update", "link", "upgrade", "up",
                 "un"}
# Programs that add a package or look one up. One of these programs given a verb of PACKAGE_VERBS_AND_LOOKUPS is a
# package step.
PACKAGE_MANAGERS = {"pip", "pip3", "uv", "npm", "pnpm", "yarn", "bun", "poetry", "pipenv", "pdm", "cargo", "pipx",
                    "brew", "apt", "apt-get", "dnf", "yum", "apk"}
PACKAGE_VERBS_AND_LOOKUPS = PACKAGE_VERBS | {"show", "list", "ls", "info", "view", "download", "search", "why",
                                             "outdated"}
# The package-manager flags that take a value word, which is no verb. `-w` takes one in npm only; elsewhere it is a
# switch (pnpm `--workspace-root`).
PACKAGE_VALUE_FLAGS = {"--prefix", "--filter", "-F", "--dir", "-w", "--workspace", "--cwd", "-C"}
LOOKUP_PROGRAMS = {"which", "whereis", "type"}
# A package runner's argument that runs the next word as a program (`npm exec jest`, `bun x vitest`).
PACKAGE_EXEC_WORDS = (["exec"], ["x"], ["dlx"])
CHECK_SCRIPTS = {"test", "lint", "typecheck", "type-check", "check", "build"}
# A `cargo test` run of a whole workspace or of every target kind is no named target.
CARGO_WHOLE_TREE_FLAGS = {"--workspace", "--all", "--all-targets"}
# The `cargo test` flags that pick a crate or a target kind, which still runs a crate's whole suite. A run limited by
# them alone is no named target for the repeat cap. The first three take a value.
CARGO_CRATE_VALUE_FLAGS = {"-p", "--package", "--exclude"}
CARGO_CRATE_WIDE_FLAGS = CARGO_CRATE_VALUE_FLAGS | {"--tests", "--bins", "--benches", "--examples", "--ignored"}


def matches_prefix(words, prefix):
    if len(words) < len(prefix):
        return False
    for word, expected in zip(words, prefix, strict=False):
        script_variant = expected in SCRIPT_VARIANT_WORDS and word.startswith(expected + ":")
        if word != expected and not script_variant:
            return False
    return True


def pytest_testpaths(repo_dir):
    # The directories the repo's pytest config names as `testpaths`: pytest.ini, pyproject.toml
    # [tool.pytest.ini_options], tox.ini [pytest] and setup.cfg [tool:pytest]. Empty when none names any.
    testpaths = set()
    for options in pytest_options(repo_dir):
        value = options.get("testpaths", [])
        names = value.split() if isinstance(value, str) else [name for name in value if isinstance(name, str)]
        testpaths |= {os.path.normpath(name) for name in names}
    return testpaths


def test_root_directories(repo_dir):
    # The paths that a test path may name to run the whole suite: the folders or files the pytest
    # `testpaths` name (globs expanded), else the top-level `tests` folder when it is a folder in the repo.
    repo_path = pathlib.Path(repo_dir)
    testpaths = pytest_testpaths(repo_dir)
    if not testpaths:
        return {"tests"} if (repo_path / "tests").is_dir() else set()

    roots = set()
    for testpath in testpaths:
        if os.path.isabs(testpath):
            continue
        matches = repo_path.glob(testpath)
        roots |= {os.path.normpath(match.relative_to(repo_path)) for match in matches if match.exists()}
    return roots


def direct_check_scope(words, cwd=None):
    # "whole" for a build or a test or lint run with no path, test name, changed-files flag or exclude flag,
    # "targeted" for one with, "none" for any other command and for a whole run of a runner in RUNNER_VALUE_FLAGS.
    # After a pytest prefix, path words that name every test root of cwd between them are no scope; naming only some
    # is a scope.
    # The caller has peeled the runner wrappers. A python program is judged by its basename.
    if words and PYTHON_PROGRAM.fullmatch(os.path.basename(words[0])):
        words = ["python", *words[1:]]
    elif words and os.path.basename(words[0]) == "manage.py":
        words = ["python", *words]

    if any(matches_prefix(words, prefix) for prefix in BUILD_PREFIXES):
        return "whole"

    if len(words) >= 3 and words[0] == "python" and os.path.basename(words[1]) == "manage.py" \
            and words[2] == "test":
        leave_out_words = [word for word in words[3:] if word.split("=", 1)[0] in LEAVES_OUT_FLAGS["manage.py"]]
        labels = [word for word in without_flag_values(words[3:], MANAGE_TEST_VALUE_OPTIONS)
                  if not word.startswith("-")]
        return "targeted" if labels or leave_out_words else "whole"

    for prefix in CHECK_RUN_PREFIXES:
        if not matches_prefix(words, prefix):
            continue
        leave_out_flags = LEAVES_OUT_FLAGS["ruff"] if prefix == ["ruff", "check"] else CHECK_RUN_LEAVES_OUT_FLAGS
        roots = test_root_directories(cwd) if cwd is not None and prefix in PYTEST_RUN_PREFIXES else frozenset()
        named_roots = {os.path.normpath(word) for word in words[len(prefix):]} & roots
        # Naming one root of several leaves the others out, so the roots are no scope only when all are named.
        roots = roots if named_roots == roots else frozenset()
        # A word that starts with a selection flag has its value attached (`-kfoo`, `--testNamePattern=foo`); the
        # space form already reads its value as a scope word.
        selection_flags = () if prefix == ["ruff", "check"] else SELECTION_VALUE_FLAGS
        scope_words = [word for word in words[len(prefix):]
                      if word.startswith(CHANGED_FILES_FLAGS) or word.startswith(selection_flags)
                      or word.split("=", 1)[0] in leave_out_flags
                      or not (word.startswith("-") or word == "run" or word in WHOLE_PACKAGE_PATHS
                              or os.path.normpath(word) in roots)]
        return "targeted" if scope_words else "whole"
    if names_unittest_module(words):
        return "targeted"
    return "targeted" if runner_names_part_of_suite(words) else "none"


def names_unittest_module(words):
    # True for `python -m unittest` given a test name, a module, a selection flag (-k, -p, --pattern) or `discover`
    # with both a start directory and a pattern. A bare run and `discover` with at most a start directory run the
    # suite and stay "none".
    if words[:len(UNITTEST_PREFIX)] != UNITTEST_PREFIX:
        return False

    unittest_words = words[len(UNITTEST_PREFIX):]
    if any(word.startswith(UNITTEST_SELECTION_FLAGS) for word in unittest_words):
        return True

    positional_words = [word for word in unittest_words if not word.startswith("-")]
    if not positional_words:
        return False
    if positional_words[0] != "discover":
        return True

    # `discover` takes its start directory and pattern positionally; -s and -t carry theirs as the next word.
    discover_words = unittest_words[unittest_words.index("discover") + 1:]
    discover_positionals = [word for word in without_flag_values(discover_words, DISCOVER_VALUE_OPTIONS)
                            if not word.startswith("-")]
    return len(discover_positionals) > 1


def launched_runner(words):
    # The words of the runner that a launcher such as npx or bundle exec runs, else the words as they are.
    for launcher in RUNNER_LAUNCHERS:
        if words[:len(launcher)] == launcher:
            return words[len(launcher):]
    return words


def runner_names_part_of_suite(words):
    # True when a runner of RUNNER_VALUE_FLAGS runs on part of its suite: a positional word or a selector flag. Its
    # whole run stays "none", so a caller that acts on "whole" reads these runners as before. A nextest
    # `--run-ignored only` and a libtest `--ignored` run only the ignored tests, so they count as part of the suite.
    runner_words = launched_runner(words)
    program = os.path.basename(runner_words[0]) if runner_words else ""
    if program not in RUNNER_VALUE_FLAGS:
        return False

    selector_value_flags = RUNNER_SELECTOR_VALUE_FLAGS.get(program, set())
    selector_flags = selector_value_flags | RUNNER_SELECTOR_SWITCHES.get(program, set())
    if program == "cargo" and runs_only_ignored_tests(runner_words[1:]):
        return True

    run_words = without_flag_values(runner_words[1:], RUNNER_VALUE_FLAGS[program] | selector_value_flags)
    # A +toolchain word is cargo's, not a scope. A bare "." names the whole package for every runner but go, where
    # `go test .` runs one package.
    whole_package_words = set() if program == "go" else WHOLE_PACKAGE_PATHS
    positional_words = [word for word in run_words
                        if not word.startswith(("-", "+")) and word != WHOLE_GO_MODULE
                        and word not in whole_package_words]
    if program in SUBCOMMAND_RUNNERS:
        subcommand_length = len(NEXTEST_SUBCOMMAND) if positional_words[:2] == NEXTEST_SUBCOMMAND else 1
        positional_words = positional_words[subcommand_length:]

    flag_names = {word.split("=", 1)[0] for word in run_words if word.startswith("-")}
    return bool(flag_names & selector_flags or positional_words)


def runs_only_ignored_tests(cargo_words):
    # True when a nextest --run-ignored flag, as `--run-ignored only` or `--run-ignored=only`, runs only the ignored
    # tests.
    for index, word in enumerate(cargo_words):
        if word.startswith("--run-ignored="):
            ignored_value = word.split("=", 1)[1]
        elif word == "--run-ignored" and index + 1 < len(cargo_words):
            ignored_value = cargo_words[index + 1]
        else:
            continue

        if ignored_value in NEXTEST_IGNORED_ONLY_VALUES:
            return True
    return False


class CheckScan:
    # What a command line runs: the widest scope found, and the make recipe commands that run a whole suite.
    def __init__(self):
        self.scope = "none"
        self.whole_recipes = []
        self.visited_depths = {}

    def note(self, scope):
        if SCOPE_RANK[scope] > SCOPE_RANK[self.scope]:
            self.scope = scope

    def runs_whole(self):
        return self.scope == "whole"


def scan_command(command, cwd, scan, depth=0, recipe=None):
    # recipe is (the make call, the target) while the command is a line of a make recipe.
    try:
        simple_command_list = split_simple_commands(command)
    except ValueError:
        # The split cannot trust some valid shell, such as $'...' quotes. Let the command through.
        scan.note("unresolved")
        return

    for words in simple_command_list:
        written_command = shlex.join(words)
        command_words = without_assignments(words)
        assigned_names = {word.split("=", 1)[0] for word in words[:len(words) - len(command_words)]}
        words = command_words
        moved_cwd = cwd_after_cd(words, cwd)
        if moved_cwd is not None:
            cwd = moved_cwd
            continue
        scan_words(words, written_command, cwd, scan, depth, recipe, assigned_names)


def cwd_after_cd(words, cwd):
    # The directory a bare `cd X` (the words of one simple command) moves to, or None when the command is no such cd.
    if len(words) == 2 and words[0] == "cd":
        return pathlib.Path(cwd) / words[1]
    return None


def cwd_after_command(command, cwd):
    # The directory the shell is in after the command: each bare `cd X` among its simple commands, in order, moves it.
    # The cwd unchanged when the text cannot be split.
    try:
        simple_command_list = split_simple_commands(command)
    except ValueError:
        return cwd

    for words in simple_command_list:
        moved_cwd = cwd_after_cd(without_assignments(words), cwd)
        if moved_cwd is not None:
            cwd = moved_cwd
    return cwd


def dropped_assignment_names(words, peeled_words):
    # The names of the NAME=value words in the prefix that command_after_wrappers dropped from words.
    dropped_words = words[:len(words) - len(peeled_words)]
    return {word.split("=", 1)[0] for word in dropped_words if "=" in word and not word.startswith("-")}


def scan_words(words, written_command, cwd, scan, depth, recipe, assigned_names=frozenset()):
    # written_command is the simple command as written, with its NAME=value words and any docker call; words are
    # the same command with the NAME=value words dropped, which is what gets judged. assigned_names holds the names
    # of the NAME=value words that came before the command.
    peeled_words = command_after_wrappers(words, peel_containers=False)
    assigned_names = assigned_names | dropped_assignment_names(words, peeled_words)
    words = peeled_words
    inner_words = unwrap_docker(words)
    forwarded_names = docker_forwarded_variables(words)
    set_names = docker_set_variables(words)
    if inner_words is not None:
        peeled_inner_words = command_after_wrappers(inner_words, peel_containers=False)
        set_names = set_names | dropped_assignment_names(inner_words, peeled_inner_words)
        words = peeled_inner_words
    if not words:
        return

    if pathlib.PurePath(words[0]).name in MAKE_PROGRAMS:
        # A NAME=value right before make can narrow the target, as one after it does. One before a docker call
        # reaches the make inside the container only when the call forwards it with -e NAME or --env NAME. A docker
        # -e NAME=value or --env NAME=value sets one inside the container, so it reaches the make as well, as does
        # one set by a wrapper inside the container (docker exec x env NAME=v make).
        reaches_make = assigned_names if inner_words is None else (assigned_names & forwarded_names) | set_names
        if reaches_make:
            scan.note("unresolved")
            return
        scan_make(words, written_command, cwd, scan, depth, recipe)
        return

    scope = direct_check_scope(words, cwd)
    scan.note(scope)
    if scope == "whole" and recipe:
        scan.whole_recipes.append((*recipe, written_command))


def scan_make(words, written_command, cwd, scan, depth, recipe):
    arguments = parse_make_arguments(words[1:])
    # Printing the commands (-n), answering a question (-q), touching the targets (-t) or printing help (-h) runs no
    # recipe line except one marked `+` or one that names `$(MAKE)`, which is not judged.
    if arguments.runs_no_recipe:
        return

    # A NAME=value argument can narrow the target, so the coder gate and a full-check receipt both let the call
    # through.
    if arguments.has_variable_assignment or depth >= MAX_MAKE_DEPTH:
        scan.note("unresolved")
        return

    directory = pathlib.Path(cwd) / arguments.directory
    makefile = load_makefile(directory, arguments.files)
    if makefile is None:
        scan.note("unresolved")
        return

    make_call = recipe[0] if recipe else written_command
    targets = arguments.targets or [makefile.default_goal]
    for target in targets:
        if target is None or not makefile.has_rule(target):
            scan.note("unresolved")
            continue
        scan_target(makefile, (directory, tuple(arguments.files)), target, scan, depth + 1, make_call)


def scan_target(makefile, makefile_key, target, scan, depth, make_call):
    visit_key = (*makefile_key, target)
    # A target scanned at a shallower depth has had all of its prerequisites and recipe read.
    scanned_depth = scan.visited_depths.get(visit_key)
    if scanned_depth is not None and scanned_depth <= depth:
        return

    if depth > MAX_MAKE_DEPTH:
        scan.note("unresolved")
        return
    scan.visited_depths[visit_key] = depth

    # A prerequisite with no rule is a file, not a target.
    for prerequisite in makefile.all_prerequisites(target):
        if makefile.has_rule(prerequisite):
            scan_target(makefile, makefile_key, prerequisite, scan, depth + 1, make_call)

    directory = makefile_key[0]
    for recipe_command in makefile.recipe_commands(target):
        scan_command(recipe_command, directory, scan, depth, (make_call, target))


def scanned_command(command, cwd):
    scan = CheckScan()
    scan_command(command, cwd, scan)
    return scan


def command_check_scope(command, cwd):
    # "whole" when the command runs a whole test suite, lint or build, "targeted" when it runs one on named files,
    # "unresolved" when what it runs cannot be read from the text (the coder gate and the full-check receipt both let
    # it through), else "none". A make target or docker exec is judged by the commands it runs.
    return scanned_command(command, cwd).scope


def step_check_scope(step, cwd):
    """The check scope of one step. A step that joins commands with `;`, `||` or a pipe is "targeted" when any of its
    test commands is targeted, since the scan keeps only the widest scope and a whole lint would hide a test run on
    one file. Each piece is judged in the directory the earlier `cd X` pieces moved to."""
    piece_cwd = cwd
    for _operator, piece in split_command_steps(step):
        piece = piece.strip()
        if runs_tests(piece) and command_check_scope(piece, piece_cwd) == "targeted":
            return "targeted"
        piece_cwd = cwd_after_command(piece, piece_cwd)
    return command_check_scope(step, cwd)


def and_step_scopes(command, cwd):
    """[(step, its check scope)] for each && step of the command (the whole command when it joins its steps another
    way). A `cd X` step moves the directory the later steps are judged in."""
    step_scopes = []
    for step in and_steps_or_whole(command):
        step_scopes.append((step, step_check_scope(step, cwd)))
        cwd = cwd_after_command(step, cwd)
    return step_scopes


def runs_whole_check(command, cwd):
    # True when the command runs a whole test suite, lint or build.
    return scanned_command(command, cwd).runs_whole()


def runs_cargo_clippy(command):
    # True when a step of the command runs `cargo clippy` once its wrappers are peeled: `cd crate && cargo clippy`,
    # `nice -n 19 cargo +nightly clippy`. A quoted "cargo clippy" is one word of another command, so it is no run.
    for words in resolved_command_words(command):
        if os.path.basename(words[0]) != "cargo":
            continue

        subcommand_words = without_flag_values(words[1:], RUNNER_VALUE_FLAGS["cargo"])
        cargo_words = [word for word in subcommand_words if not word.startswith(("+", "-"))]
        if cargo_words[:1] == ["clippy"]:
            return True
    return False


def runs_tests(command):
    """True when a step of the shell command runs tests: a word that is `pytest`, `vitest`, `jest` or `mocha`, or
    `test`, `nextest` or a script or target name that starts `test:` or `test-`, given to a script runner (`npm test`,
    `make test-unit`, `pnpm --filter api test`, `python manage.py test`, `cargo nextest run`). A search, a file
    check, a `cd`, a tool whose argument merely names a test folder, or a package-verb step whose `test-` word names
    a package (`npm install test-x`) is not. False for text shlex cannot split."""
    try:
        simple_command_list = split_simple_commands(command)
    except ValueError:
        return False

    return any(step_runs_tests(without_assignments(words)) for words in simple_command_list)


def step_runs_tests(words):
    # True when one step (assignments already removed) runs tests, by a runner word, a `-m unittest` module run or a
    # script runner's test word.
    if not words or words[0] in NON_TEST_PROGRAMS:
        return False

    return (any(word in TEST_RUNNER_WORDS for word in words) or contains_word_run(words, UNITTEST_MODULE_WORDS)
            or step_runs_test_script(words))


def step_installs_or_looks_up(words):
    # True when the step is a `PACKAGE_MANAGERS` step with a verb of `PACKAGE_VERBS_AND_LOOKUPS`, a
    # `LOOKUP_PROGRAMS` step, or `command -v` (`pip install pytest`, `pip show pytest`,
    # `npm install -D jest`, `uv add pytest`, `which pytest`, `command -v pytest`): a runner word there names a
    # package, not a run.
    program = os.path.basename(words[0])
    if program in LOOKUP_PROGRAMS:
        return True

    if program == "command":
        return bool({"-v", "-V"}.intersection(words[1:2]))

    return package_manager_verb(words) in PACKAGE_VERBS_AND_LOOKUPS


def package_manager_verb(words):
    # The verb of a package-manager step: the first word after the program that is no flag, or the second after
    # `uv pip` or `uv tool`. `python -m pip` is `pip`. None when the step is no package-manager step.
    program = os.path.basename(words[0])
    arguments = words[1:]
    if PYTHON_PROGRAM.fullmatch(program):
        if arguments[:2] != ["-m", "pip"]:
            return None
        arguments = arguments[2:]
    elif program not in PACKAGE_MANAGERS:
        return None

    value_flags = PACKAGE_VALUE_FLAGS if program == "npm" else PACKAGE_VALUE_FLAGS - {"-w"}
    flagless_arguments = without_flag_values(arguments, value_flags)
    verb_words = [word for word in flagless_arguments if not word.startswith("-")]
    if program == "uv" and verb_words[:1] in (["pip"], ["tool"]):
        verb_words = verb_words[1:]
    if program == "yarn" and verb_words[:1] == ["global"]:
        verb_words = verb_words[1:]
    elif program == "yarn" and verb_words[:1] == ["workspace"]:
        verb_words = verb_words[2:]
    return verb_words[0] if verb_words else None


def step_runs_test_script(words):
    # True when a script runner in the step is followed by a test word (`npm test`, `make test-unit`, `cargo nextest`).
    # A package manager's verb in command position (`npm install test-x`) names a package to change, not a test.
    if package_manager_verb(words) in PACKAGE_VERBS:
        return False

    runner_seen = False
    for word in words:
        if runner_seen and TEST_WORD.match(word):
            return True
        if pathlib.PurePosixPath(word).name in SCRIPT_RUNNERS:
            runner_seen = True
    return False


def names_test_runner(command):
    # True when the command text names a test runner anywhere, a search or print step included. runs_tests is the
    # narrower reading; a caller that must not miss a runner takes either.
    return bool(TEST_RUNNER.search(command))


def prints_own_runner_summary(command):
    """False when no step of the shell command can print a runner summary of its own: every step is a search, a file
    print, a `cd` or similar program, or is negated with `!`, so the answer gates only the no-test-matched check. True
    for any other step (a test runner or a script wrapper such as `bash tests/run.sh`) and for text shlex cannot
    split."""
    try:
        simple_command_list = split_simple_commands(command)
    except ValueError:
        return True

    for words in simple_command_list:
        words = without_assignments(words)
        if words and words[0] != "!" and words[0] not in NON_TEST_PROGRAMS:
            return True
    return False


def names_django_test_run(command):
    # True when the command text names `manage.py test`, a command that only names it included.
    return bool(DJANGO_TEST_RUN.search(command))


def runner_family(command):
    # The runner families the command runs, as a set of "js", "python" and "cargo", read from its text. Empty when it
    # names none of them, such as `make test-consistency` or `just test`.
    return {family for family, runs_family in RUNNER_FAMILY_PATTERNS.items() if runs_family.search(command)}


def cargo_test_arguments(words):
    # The words after `cargo [+toolchain] test`, or None when the step is no `cargo test`.
    if not words or os.path.basename(words[0]) != "cargo":
        return None
    cargo_words = [word for word in words[1:] if not word.startswith("+")]
    return cargo_words[1:] if cargo_words[:1] == ["test"] else None


def names_test_filter(command):
    # True when the command names which tests to run: a filter flag, or a `cargo test` with a name or any word after
    # `--`. A cargo option's value (`-p core`) is no filter.
    if TEST_FILTER.search(command):
        return True

    cargo_value_flags = RUNNER_VALUE_FLAGS["cargo"] | RUNNER_SELECTOR_VALUE_FLAGS["cargo"]
    for words in step_words(command):
        arguments = cargo_test_arguments(words)
        if arguments is None:
            continue
        if "--" in arguments[:-1]:
            return True
        option_words = arguments[:arguments.index("--")] if "--" in arguments else arguments
        run_words = without_flag_values(option_words, cargo_value_flags)
        if any(not word.startswith("-") for word in run_words):
            return True
    return False


def words_run_a_check(words):
    # True when the step is a test, lint, typecheck or build run: a program of CHECK_PROGRAMS, a subcommand of
    # CHECK_SUBCOMMANDS, a package script of CHECK_SCRIPTS, or anything direct_check_scope reads as a check.
    words = launched_runner(words)
    if not words:
        return False

    program = os.path.basename(words[0])
    if program in CHECK_PROGRAMS:
        return True

    arguments = [word for word in words[1:] if not word.startswith("+")] if program == "cargo" else words[1:]
    if program in CHECK_SUBCOMMANDS:
        return bool(arguments) and arguments[0] in CHECK_SUBCOMMANDS[program]

    if program in PACKAGE_SCRIPT_RUNNERS:
        script_words = arguments[1:] if arguments[:1] == ["run"] else arguments
        if script_words[:1] and script_words[0] in CHECK_SCRIPTS:
            return True
        if arguments[:1] in PACKAGE_EXEC_WORDS:
            return words_run_a_check(arguments[1:])
    return direct_check_scope(words) != "none"


def is_check(command):
    # True when a step of the command is a test, lint, typecheck or build run, whole or on named files, or a
    # script runner given a test word, or any other step that runs tests (a runner word anywhere in the step). A
    # `PACKAGE_MANAGERS` step with a verb of `PACKAGE_VERBS_AND_LOOKUPS`, a `LOOKUP_PROGRAMS` step, or `command -v`
    # is no check, even when it names a runner.
    return any(not step_installs_or_looks_up(words)
               and (words_run_a_check(words) or step_runs_tests(words))
               for words in step_words(command))


def without_crate_wide_flags(flag_words):
    # The cargo flags without the CARGO_CRATE_WIDE_FLAGS, as `-p core`, `--package=core` or `--tests`.
    value_free_words = without_flag_values(flag_words, CARGO_CRATE_VALUE_FLAGS)
    return [word for word in value_free_words if word.split("=", 1)[0] not in CARGO_CRATE_WIDE_FLAGS]


def names_cargo_test_target(command):
    # True when a `cargo test` in the command names a test target for the repeat cap: --lib, --doc, --test, --bin,
    # --example or --bench with a name, or a test-name filter. A run of a whole workspace, of every target kind, of a
    # chosen crate (-p) or with no scope is a full suite. Words after `--` are the test binary's, not a target.
    for words in step_words(command):
        arguments = cargo_test_arguments(words)
        if arguments is None:
            continue

        option_words = arguments[:arguments.index("--")] if "--" in arguments else arguments
        if CARGO_WHOLE_TREE_FLAGS & set(option_words):
            continue

        target_words = without_crate_wide_flags(option_words)
        if runner_names_part_of_suite(["cargo", "test", *target_words]):
            return True
    return False
