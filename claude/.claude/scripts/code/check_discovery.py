"""The full check of a repo that names none, found from the repo's own files.

In order: the Makefile `check` target (`make check`), the package.json `check` script (run with the repo's package
manager), then the repo's lint, type check and tests joined with `&&`, built from what gate_commands.py already reads:
a package's lint and type-check scripts, ruff, and the repo's own test command (the Makefile `test` target, else the
package.json `test` script). Only a repo that names no test command gets a guessed runner: its vitest or jest
dependency, Django's `manage.py test` or pytest. None when the repo's files give no command."""
import json
import pathlib
import shlex
import sys

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(SCRIPTS_DIR / "lib"), str(SCRIPTS_DIR / "code")]

import gate_commands
import makefile_text
import pytest_config

CHECK_TARGET = "check"
TEST_TARGET = "test"
# The lock file that names a package manager, then the program that runs a package script and the one that runs a
# binary the package depends on.
PACKAGE_MANAGERS = (("pnpm-lock.yaml", "pnpm", "pnpm exec"), ("yarn.lock", "yarn", "yarn"))
DEFAULT_PACKAGE_MANAGER = ("npm", "npx")


def package_manager(repo_dir):
    """(the program that runs a package script, the program that runs a dependency's binary) by the repo's lock file:
    pnpm-lock.yaml pnpm, yarn.lock yarn, else npm."""
    for lock_file, program, binary_runner in PACKAGE_MANAGERS:
        if (repo_dir / lock_file).is_file():
            return program, binary_runner
    return DEFAULT_PACKAGE_MANAGER


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

    program, _ = package_manager(repo_dir)
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

    program, _ = package_manager(repo_dir)
    return f"{program} {TEST_TARGET}"


def package_part_commands(repo_dir, guesses_tests):
    """The lint, type check and, when `guesses_tests`, the test runner its dependencies name, of the repo's root
    package, in that order."""
    package = read_package_json(repo_dir)
    if not package:
        return []

    scripts = package.get("scripts", {})
    dependencies = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
    program, binary_runner = package_manager(repo_dir)
    commands = []

    if "lint" in scripts:
        commands.append(f"{program} run lint")
    elif "eslint" in dependencies:
        commands.append(f"{binary_runner} eslint .")

    typecheck_name = gate_commands.typecheck_script_name(scripts)
    if typecheck_name:
        commands.append(f"{program} run {typecheck_name}")
    elif (repo_dir / "tsconfig.json").is_file():
        commands.append(f"{binary_runner} tsc --noEmit")

    runner, _ = gate_commands.js_test_runner(dependencies, scripts)
    if guesses_tests and runner:
        commands.append(f"{binary_runner} {runner}")
    return commands


def python_part_commands(repo_dir, guesses_tests):
    """The ruff check and, when `guesses_tests`, the tests of a Python repo: `manage.py test` for a Django repo with
    no pytest-django settings, else pytest."""
    runs_django = (repo_dir / "manage.py").is_file() and not pytest_config.has_django_settings(repo_dir)
    runs_pytest = bool(pytest_config.pytest_options(repo_dir)) or (repo_dir / "conftest.py").is_file() \
        or (repo_dir / "tests").is_dir()
    if not (runs_django or runs_pytest):
        return []

    runner = gate_commands.project_python_runner(repo_dir) or ["python3", "-m"]
    commands = []
    ruff_command = gate_commands.ruff_check_command(repo_dir, runner)
    if ruff_command:
        commands.append(ruff_command)

    if not guesses_tests:
        return commands

    if runs_django:
        python_words = runner[:-1] if runner[-1:] == ["-m"] else [*runner, "python"]
        commands.append(shlex.join([*python_words, "manage.py", "test", "--noinput"]))
    else:
        commands.append(shlex.join([*runner, "pytest"]))
    return commands


def part_commands_check(repo_dir):
    own_tests = own_test_command(repo_dir)
    guesses_tests = own_tests is None
    commands = package_part_commands(repo_dir, guesses_tests) + python_part_commands(repo_dir, guesses_tests)
    if own_tests:
        commands.append(own_tests)
    return " && ".join(commands) or None


def discovered_check_command(repo):
    """The full check the repo's own files give, or None."""
    repo_dir = pathlib.Path(repo)
    make_check = makefile_target_command(repo_dir, CHECK_TARGET)
    return make_check or package_check_command(repo_dir) or part_commands_check(repo_dir)
