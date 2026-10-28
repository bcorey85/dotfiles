"""Reads a shell command line and says how wide a check it runs: a whole test suite, lint or build, a targeted run, or
none. A make target or a docker exec or run call is judged by the commands it runs (make is read from the Makefile
text; a NAME=value argument, a missing Makefile or a missing target lets the call through, and make -n, -q, -t or -h
runs no recipe line except one marked `+` or one that names `$(MAKE)`, which is not judged). Runner wrappers (poetry,
pipenv or uv run, env, timeout and the like) are peeled first, so the command they run is the one judged."""
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
    # with, "none" for any other command.
    # The caller has peeled the runner wrappers. A python program is judged by its basename.
    if words and PYTHON_PROGRAM.fullmatch(os.path.basename(words[0])):
        words = ["python", *words[1:]]
    elif words and os.path.basename(words[0]) == "manage.py":
        words = ["python", *words]

    if any(matches_prefix(words, prefix) for prefix in BUILD_PREFIXES):
        return "whole"

    if len(words) >= 3 and words[0] == "python" and os.path.basename(words[1]) == "manage.py" \
            and words[2] == "test":
        labels = []
        skip_value = False
        for word in words[3:]:
            if skip_value:
                skip_value = False
            elif word in MANAGE_TEST_VALUE_OPTIONS:
                skip_value = True
            elif not word.startswith("-"):
                labels.append(word)
        return "targeted" if labels else "whole"

    for prefix in CHECK_RUN_PREFIXES:
        if not matches_prefix(words, prefix):
            continue
        scope_words = [word for word in words[len(prefix):]
                      if word.startswith(CHANGED_FILES_FLAGS)
                      or not (word.startswith("-") or word == "run" or word in WHOLE_PACKAGE_PATHS)]
        return "targeted" if scope_words else "whole"
    return "none"


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
