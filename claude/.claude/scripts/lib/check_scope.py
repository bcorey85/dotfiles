"""Reads a shell command line and says how wide a check it runs: a whole test suite, lint or build, a targeted run, or
none. A whole run of a runner in RUNNER_VALUE_FLAGS reads none, not whole. A make target or a docker exec or run call
is judged by the commands it runs (make is read from the Makefile text; a NAME=value argument, a missing Makefile or a
missing target lets the call through, and make -n, -q, -t or -h runs no recipe line except one marked `+` or one that
names `$(MAKE)`, which is not judged). Runner wrappers (poetry, pipenv or uv run, env, timeout and the like) are peeled
first, so the command they run is the one judged."""
import os
import pathlib
import re
import shlex

from makefile_text import load_makefile, parse_make_arguments
from shell_command import (
    command_after_wrappers,
    docker_forwarded_variables,
    docker_set_variables,
    split_simple_commands,
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

# A simple command that starts with one of these runs tests or lint. With no path, test name or changed-files flag
# after it, it covers the whole package. "test" and "lint" also match script names such as "test:unit".
CHECK_RUN_PREFIXES = [
    ["npm", "test"], ["npm", "t"], ["npm", "run", "test"], ["yarn", "test"], ["yarn", "run", "test"],
    ["pnpm", "test"], ["pnpm", "run", "test"], ["bun", "test"], ["npx", "vitest"], ["npx", "jest"],
    ["vitest"], ["jest"], ["pytest"], ["python", "-m", "pytest"],
    ["npm", "run", "lint"], ["yarn", "lint"], ["yarn", "run", "lint"], ["pnpm", "lint"], ["pnpm", "run", "lint"],
    ["npx", "eslint"], ["eslint"], ["ruff", "check"],
]
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
              "-A", "-W", "--test-threads", "--color", "--message-format", "--config", "-Z", "--exclude", "--retries",
              "--failure-output", "--success-output", "--status-level", "--final-status-level",
              "--max-fail", "--cargo-profile", "--archive-file", "--format", "--logfile", "-P", "--run-ignored"},
    "go": {"-p", "-coverprofile", "-o", "-count", "-timeout", "-parallel", "-tags", "-cpu", "-covermode",
           "-shuffle", "-mod", "-vet", "-gcflags", "-ldflags", "-asmflags", "-exec", "-modfile", "-overlay",
           "-coverpkg", "-bench", "-benchtime", "-blockprofile", "-blockprofilerate", "-cpuprofile", "-memprofile",
           "-memprofilerate", "-mutexprofile", "-mutexprofilefraction", "-trace", "-outputdir", "-testlogfile",
           "-fuzztime", "-fuzzminimizetime", "-pgo", "-buildmode", "-buildvcs", "-toolexec", "-compiler",
           "-installsuffix", "-list"},
    "mypy": {"--python-version", "--config-file", "--cache-dir", "--python-executable", "--platform", "--exclude",
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
              "--exclude-pattern", "--failure-exit-code", "--deprecation-out", "-O", "--options"},
    "phpunit": {"-c", "--configuration", "--log-junit", "--bootstrap", "-d", "--exclude-group", "--coverage-clover",
                "--coverage-html", "--coverage-xml", "--testdox-html", "--cache-result-file", "--order-by",
                "--random-order-seed", "--printer", "--test-suffix", "--extensions", "--cache-directory",
                "--processes", "--log-tap"},
}
# By runner: the flags that pick part of the suite and take a value, as `--flag value` or `--flag=value`.
RUNNER_SELECTOR_VALUE_FLAGS = {
    "cargo": {"-p", "--package", "--test", "--bench", "--bin", "--example", "-E", "--filterset", "--filter-expr",
              "--skip", "--partition"},
    "go": {"-run", "-skip", "-fuzz"},
    "mypy": {"-p", "--package", "-m", "--module"},
    "dotnet": {"--filter"},
    "rspec": {"-e", "--example", "-t", "--tag", "-P", "--pattern"},
    "phpunit": {"--filter", "--testsuite", "--group"},
    "bats": {"--filter", "-f", "--filter-tags"},
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


def matches_prefix(words, prefix):
    if len(words) < len(prefix):
        return False
    for word, expected in zip(words, prefix, strict=False):
        script_variant = expected in SCRIPT_VARIANT_WORDS and word.startswith(expected + ":")
        if word != expected and not script_variant:
            return False
    return True


def direct_check_scope(words):
    # "whole" for a build or a test or lint run with no path, test name or changed-files flag, "targeted" for one
    # with, "none" for any other command and for a whole run of a runner in RUNNER_VALUE_FLAGS.
    # The caller has peeled the runner wrappers. A python program is judged by its basename.
    if words and PYTHON_PROGRAM.fullmatch(os.path.basename(words[0])):
        words = ["python", *words[1:]]
    elif words and os.path.basename(words[0]) == "manage.py":
        words = ["python", *words]

    if any(matches_prefix(words, prefix) for prefix in BUILD_PREFIXES):
        return "whole"

    if len(words) >= 3 and words[0] == "python" and os.path.basename(words[1]) == "manage.py" \
            and words[2] == "test":
        labels = [word for word in without_flag_values(words[3:], MANAGE_TEST_VALUE_OPTIONS)
                  if not word.startswith("-")]
        return "targeted" if labels else "whole"

    for prefix in CHECK_RUN_PREFIXES:
        if not matches_prefix(words, prefix):
            continue
        scope_words = [word for word in words[len(prefix):]
                      if word.startswith(CHANGED_FILES_FLAGS)
                      or not (word.startswith("-") or word == "run" or word in WHOLE_PACKAGE_PATHS)]
        return "targeted" if scope_words else "whole"
    return "targeted" if runner_names_part_of_suite(words) else "none"


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
        if len(words) == 2 and words[0] == "cd":
            cwd = pathlib.Path(cwd) / words[1]
            continue
        scan_words(words, written_command, cwd, scan, depth, recipe, assigned_names)


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

    scope = direct_check_scope(words)
    scan.note(scope)
    if scope == "whole" and recipe:
        scan.whole_recipes.append((*recipe, written_command))


def scan_make(words, written_command, cwd, scan, depth, recipe):
    arguments = parse_make_arguments(words[1:])
    # Printing the commands (-n), answering a question (-q), touching the targets (-t) or printing help (-h) runs no
    # recipe line except one marked `+` or one that names `$(MAKE)`, which is not judged.
    if arguments.runs_no_recipe:
        return

    # A NAME=value argument can narrow the target, so the call is let through.
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
    # "unresolved" when what it runs cannot be read from the text (so it is let through), else "none". A make target
    # or docker exec is judged by the commands it runs.
    return scanned_command(command, cwd).scope


def runs_whole_check(command, cwd):
    # True when the command runs a whole test suite, lint or build.
    return scanned_command(command, cwd).runs_whole()
