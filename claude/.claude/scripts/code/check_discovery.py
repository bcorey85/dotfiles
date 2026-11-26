"""The full check of a repo that names none, found from the repo's own files.

In order: the Makefile `check` target (`make check`), the package.json `check` script (run with the repo's package
manager), then the repo's lint, type check and tests, built from what gate_commands.py already reads:
a package's lint and type-check scripts, ruff, and the repo's own test command (the Makefile `test` target, else the
package.json `test` script). Only a repo that names no test command gets a guessed runner: its vitest or jest
dependency, Django's `manage.py test` or pytest. The steps of one part join with `&&`. With changed paths, only the
part whose path kind a changed path has runs (the package part owns JS/TS/CSS paths and package.json, the Python part
.py and Python config paths; an HTML or JSON file counts as both); a doc path (Markdown, or under docs/) that is no
code kind is skipped; any other changed path of neither kind, no changed paths, or doc paths only runs every part.
Several parts run each on its own (lib/check_parts.py) and the run fails when any failed.
None when the repo's files give no command."""
import json
import pathlib
import shlex
import sys
from collections import namedtuple

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(SCRIPTS_DIR / "lib"), str(SCRIPTS_DIR / "code")]

import gate_commands
import makefile_text
import pytest_config
import source_paths
from check_parts import join_parts

PACKAGE_PART = "package"
PYTHON_PART = "python"
TESTS_PART = "tests"
# One check part: its name (PACKAGE_PART, PYTHON_PART, TESTS_PART) and the steps that join with &&.
CheckPart = namedtuple("CheckPart", ["name", "commands"])
CHECK_TARGET = "check"
TEST_TARGET = "test"


def read_package_json(repo_dir):
    """The repo's root package.json as a dict, or {} when there is none or it does not parse."""
    package_json = repo_dir / "package.json"
    if not package_json.is_file():
        return {}

    try:
        package = json.loads(package_json.read_text(errors="replace"))
    except json.JSONDecodeError:
        return {}
    return package if isinstance(package, dict) else {}


def makefile_target_command(repo_dir, target):
    makefile = makefile_text.load_makefile(repo_dir)
    if makefile is None or not makefile.has_rule(target):
        return None
    return f"make {target}"


def package_check_command(repo_dir):
    scripts = read_package_json(repo_dir).get("scripts", {})
    if CHECK_TARGET not in scripts:
        return None

    program = gate_commands.package_manager(repo_dir)
    return f"{program} run {CHECK_TARGET}"


def own_test_command(repo_dir):
    """The test command the repo names itself: `make test` for a Makefile `test` target, else the package.json `test`
    script run with the package manager. None when it names neither."""
    make_test = makefile_target_command(repo_dir, TEST_TARGET)
    if make_test:
        return make_test

    scripts = read_package_json(repo_dir).get("scripts", {})
    if TEST_TARGET not in scripts:
        return None

    program = gate_commands.package_manager(repo_dir)
    return f"{program} {TEST_TARGET}"


def package_part_commands(repo_dir, guesses_tests):
    """The lint, type check and, when `guesses_tests`, the test runner its dependencies name, of the repo's root
    package, in that order."""
    package = read_package_json(repo_dir)
    if not package:
        return []

    scripts = package.get("scripts", {})
    dependencies = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
    program = gate_commands.package_manager(repo_dir)
    commands = []

    if "lint" in scripts:
        commands.append(f"{program} run lint")
    elif "eslint" in dependencies:
        commands.append(gate_commands.package_binary_command(program, "", "eslint ."))

    typecheck_name = gate_commands.typecheck_script_name(scripts)
    if typecheck_name:
        commands.append(f"{program} run {typecheck_name}")
    elif (repo_dir / "tsconfig.json").is_file():
        commands.append(gate_commands.package_binary_command(program, "", "tsc --noEmit"))

    runner, _ = gate_commands.js_test_runner(dependencies, scripts)
    if guesses_tests and runner:
        commands.append(gate_commands.package_binary_command(program, "", runner))
    return commands


def wrapper_shell(script):
    """The shell a `#!` line names, for a script whose `#!` line names no Python (`#!/usr/bin/env bash` gives bash),
    else None."""
    with script.open(errors="replace") as script_file:
        first_line = script_file.readline().strip()
    if not first_line.startswith("#!") or "python" in first_line:
        return None

    shebang_words = first_line[2:].split()
    if not shebang_words:
        return None
    program = pathlib.PurePosixPath(shebang_words[0]).name
    if program == "env" and len(shebang_words) > 1:
        return shebang_words[1]
    return program


def manage_py_words(repo_dir, runner):
    """The words that run the repo-root manage.py through the project runner: its shell for a shell wrapper (the
    runner puts its environment's python on PATH for the wrapper), else python."""
    shell = wrapper_shell(repo_dir / "manage.py")
    if shell:
        environment_words = [] if runner[-1:] == ["-m"] else runner
        return [*environment_words, shell, "manage.py"]

    python_words = runner[:-1] if runner[-1:] == ["-m"] else [*runner, "python"]
    return [*python_words, "manage.py"]


def python_part_commands(repo_dir, guesses_tests, env=None):
    """The ruff check and, when `guesses_tests`, the tests of a Python repo: `manage.py test` for a Django repo with
    no pytest-django settings, else pytest."""
    runs_django = (repo_dir / "manage.py").is_file() and not pytest_config.has_django_settings(repo_dir)
    runs_pytest = bool(pytest_config.pytest_options(repo_dir)) or (repo_dir / "conftest.py").is_file() \
        or (repo_dir / "tests").is_dir()
    if not (runs_django or runs_pytest):
        return []

    runner = gate_commands.project_python_runner(repo_dir, env) or ["python3", "-m"]
    commands = []
    ruff_command = gate_commands.ruff_check_command(repo_dir, runner)
    if ruff_command:
        commands.append(ruff_command)

    if not guesses_tests:
        return commands

    if runs_django:
        commands.append(shlex.join([*manage_py_words(repo_dir, runner), "test", "--noinput"]))
    else:
        commands.append(shlex.join([*runner, "pytest"]))
    return commands


def parts_to_run(parts, changed_paths):
    """The CheckParts a change touches. A shared path (a template or a JSON file, read by both kinds of code) counts as
    both kinds. A doc path that is no code kind is skipped. A path of neither kind (root config, lock file, CI),
    no changed path, a change of doc paths only, or a change that touches no existing part runs every part."""
    if not changed_paths:
        return parts

    kinds = set()
    for path in changed_paths:
        if source_paths.is_shared_path(path):
            kinds.update((PACKAGE_PART, PYTHON_PART))
        elif source_paths.is_package_path(path):
            kinds.add(PACKAGE_PART)
        elif source_paths.is_python_path(path):
            kinds.add(PYTHON_PART)
        elif source_paths.is_doc_path(path):
            continue
        else:
            return parts

    selected = [part for part in parts if part.name in kinds]
    return selected or parts


def discovered_parts(repo_dir, changed_paths=None):
    """The CheckParts for the parts `changed_paths` touch (every part when None or empty). The repo's own test command
    is a part of its own, run after the others."""
    own_tests = own_test_command(repo_dir)
    guesses_tests = own_tests is None
    parts = [CheckPart(PACKAGE_PART, package_part_commands(repo_dir, guesses_tests)),
             CheckPart(PYTHON_PART, python_part_commands(repo_dir, guesses_tests))]
    parts = [part for part in parts if part.commands]
    parts = parts_to_run(parts, changed_paths)
    if own_tests:
        parts.append(CheckPart(TESTS_PART, [own_tests]))
    return parts


def part_commands_check(repo_dir, changed_paths=None, left_out_steps=()):
    """The discovered parts' commands, joined by join_parts, with each part's steps in `left_out_steps` taken out of
    that part first. A part left with no step is dropped; None when no part is left."""
    kept = []
    for part in discovered_parts(repo_dir, changed_paths):
        commands = [command for command in part.commands if command not in left_out_steps]
        if commands:
            kept.append(CheckPart(part.name, commands))
    if not kept:
        return None
    return join_parts(kept)


def discovered_check_steps(repo, changed_paths=None):
    """The steps of the discovered parts, in run order; empty when a Makefile or package `check` target runs as one
    command."""
    repo_dir = pathlib.Path(repo)
    if makefile_target_command(repo_dir, CHECK_TARGET) or package_check_command(repo_dir):
        return []
    return [command for part in discovered_parts(repo_dir, changed_paths) for command in part.commands]


def discovered_check_command(repo, changed_paths=None, left_out_steps=()):
    """The full check the repo's own files give, or None. `changed_paths` (relative to the repo) narrows the
    guessed parts to the ones the change touches; the Makefile and package `check` targets run as they are.
    `left_out_steps` are taken out of each guessed part."""
    repo_dir = pathlib.Path(repo)
    make_check = makefile_target_command(repo_dir, CHECK_TARGET)
    return (make_check or package_check_command(repo_dir)
            or part_commands_check(repo_dir, changed_paths, left_out_steps))
