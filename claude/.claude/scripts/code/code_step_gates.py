"""Gate commands derived from a phase section: what to run for the files the phase names."""
import configparser
import contextlib
import json
import pathlib
import re
import shlex
import tomllib

import check_scope
import plan_format
import script_utils
import test_run_output
from code_step_boundary import verification_command
from linked_installs import VENV_FOLDERS
from shell_command import command_after_wrappers, split_simple_commands

CARGO_CLIPPY = "cargo clippy --all-targets -- -D warnings"
UNKNOWN_FAMILY = "unknown"
TEST_FAMILY_PATTERNS = {
    "js": re.compile(r"\b(?:vitest|jest|mocha)\b|\b(?:npm|pnpm|yarn|bun|npx)\b.*\btest\b"),
    "python": re.compile(r"\bpytest\b|\bmanage\.py\s+test\b"),
    "cargo": re.compile(r"\bcargo\s+(?:test|nextest)\b"),
}
TYPECHECK_SCRIPTS = ["typecheck", "type-check", "check-types", "tsc"]
SCRIPT_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mts", ".mjs")
TEST_SUFFIXES = ".test.ts,.test.tsx,.spec.ts,.spec.tsx,.test.js,.test.jsx"
TEST_FILE = re.compile(r"\.(test|spec)\.|(^|/)test_[^/]*\.py$|_test\.py$")
BARE_CARGO_MANIFEST = re.compile(r"`(Cargo\.toml)`")
PATH_IN_BACKTICKS = re.compile(r"`([\w.@-]+(?:/[\w.@\[\]()-]+)+\.\w+)(?::\d+(?:-\d+)?)?`")
PYTHON_RUNNERS = (("uv.lock", ["uv", "run"]), ("poetry.lock", ["poetry", "run"]), ("pdm.lock", ["pdm", "run"]),
                  ("Pipfile.lock", ["pipenv", "run"]))
SHELL_OPERATORS = {"&&", "||", ";", "|", "&"}
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
DJANGO_TEST_FILE = re.compile(r"(^|/)test[^/]*\.py$")
# `manage.py test` asks before it deletes a test database a killed run left behind; the gate has no one to answer.
NO_INPUT_OPTIONS = {"--noinput", "--no-input"}
PYTEST_DJANGO_SETTINGS = re.compile(r"DJANGO_SETTINGS_MODULE|--ds\b", re.IGNORECASE)


def nearest_directory_with(repo_dir, rel_path, manifest_name):
    manifest = script_utils.nearest_file_upward((repo_dir / rel_path).parent, manifest_name, repo_dir)
    return manifest.parent if manifest else None


def in_directory(command, package_rel):
    return f"cd {shlex.quote(package_rel)} && {command}" if package_rel else command


def script_package_commands(repo_dir, package_dir, paths, derives_tests):
    package_json = json.loads((package_dir / "package.json").read_text())
    scripts = package_json.get("scripts", {})
    dependencies = {**package_json.get("dependencies", {}), **package_json.get("devDependencies", {})}
    package_rel = script_utils.directory_relative_to(repo_dir, package_dir)
    relative_paths = [str((repo_dir / path).relative_to(package_dir)) for path in paths]
    commands = []

    typecheck_name = next((name for name in TYPECHECK_SCRIPTS if name in scripts), None)
    if typecheck_name:
        commands.append(in_directory(f"npm run {typecheck_name}", package_rel))
    elif (package_dir / "tsconfig.json").is_file():
        commands.append(in_directory("npx tsc --noEmit", package_rel))

    source_suffixes = sorted({pathlib.Path(p).suffix for p in relative_paths
                             if p.endswith(SCRIPT_SUFFIXES) and not TEST_FILE.search(p)}
                            | {pathlib.Path(p).suffix for p in relative_paths if p.endswith(SCRIPT_SUFFIXES)})
    if ("eslint" in dependencies or "lint" in scripts) and source_suffixes:
        commands.append(in_directory("npx eslint {files:" + ",".join(source_suffixes) + "}", package_rel))

    if not derives_tests:
        return commands

    # A phase that names no script file in the package (a Python file under a folder that holds a package.json) has
    # no script test to derive.
    if not any(p.endswith(SCRIPT_SUFFIXES) for p in relative_paths):
        return commands

    test_paths = [p for p in relative_paths if TEST_FILE.search(p)]
    runner = "vitest run" if "vitest" in dependencies else "jest" if "jest" in dependencies else None
    if runner:
        scope = " ".join(shlex.quote(p) for p in test_paths) or "{files:" + TEST_SUFFIXES + "}"
        commands.append(in_directory(f"npx {runner} {scope}", package_rel))
    elif "test" in scripts:
        scope = " ".join(shlex.quote(p) for p in test_paths) or "{files:" + TEST_SUFFIXES + "}"
        commands.append(in_directory(f"npm test -- {scope}", package_rel))
    return commands


def listed_commands(repo_dir, phase_section):
    # The commands the phase's Automated Verification lists, read the way the phase boundary reads them, each once.
    listed = []
    for _, line in plan_format.automated_verification_rows(phase_section.splitlines()):
        if plan_format.runs_no_command(line):
            continue

        command = verification_command(line, repo_dir)
        if command and command not in listed:
            listed.append(command)
    return listed


def listed_words(listed):
    # The words of each listed command, leaving out one the shell splitter cannot read.
    for command in listed:
        try:
            yield shlex.split(command)
        except ValueError:
            continue


def chains_a_command(words):
    return any(word in SHELL_OPERATORS or word == "cd" for word in words)


def listed_python_runner(listed):
    # The words before `pytest` in the first listed pytest command, such as ["uv", "run"] or
    # ["DJANGO_SETTINGS_MODULE=app.test", ".venv/bin/python", "-m"], or None when it lists none. A command that
    # changes directory or chains another command before pytest gives no runner.
    for words in listed_words(listed):
        if "pytest" not in words:
            continue

        runner = words[:words.index("pytest")]
        if not chains_a_command(runner):
            return runner
    return None


def lists_pytest(listed):
    # True when any listed command runs pytest, with or without a usable runner.
    return any("pytest" in words for words in listed_words(listed))


def listed_django_test(listed):
    # (runner, options, manage script) of the first listed `<python> [<dir>/]manage.py test` command, or None when the
    # phase lists none. The runner is in the form of a pytest runner: ["uv", "run", "python", "-m"] for
    # `uv run python manage.py test`, so ruff runs through the same words. The options are the flags after `test` with
    # their values ("--keepdb", "--settings app.test"); the listed test labels are dropped, because the gate scopes
    # the run to the changed test modules. The manage script is the word as listed: `backend/manage.py`. A command
    # that chains another command first gives none.
    for words in listed_words(listed):
        manage_index = next((index for index, word in enumerate(words)
                             if pathlib.PurePosixPath(word).name == "manage.py"), None)
        if manage_index is None:
            continue

        is_test_command = words[manage_index + 1:manage_index + 2] == ["test"]
        runs_python = manage_index > 0 and pathlib.PurePosixPath(words[manage_index - 1]).name.startswith("python")
        if not (is_test_command and runs_python) or chains_a_command(words[:manage_index]):
            continue

        options = []
        after_test = words[manage_index + 2:]
        for position, word in enumerate(after_test):
            follows_value_option = position and after_test[position - 1] in check_scope.MANAGE_TEST_VALUE_OPTIONS
            if word.startswith("-") or follows_value_option:
                options.append(word)
        return [*words[:manage_index], "-m"], options, words[manage_index]
    return None


def nearest_manage_script(repo_dir, python_paths):
    # The repo-relative path of the manage.py nearest above the first Python path that has one, else None.
    for path in python_paths:
        manage_dir = nearest_directory_with(repo_dir, path, "manage.py")
        if manage_dir is not None:
            return (manage_dir / "manage.py").relative_to(repo_dir).as_posix()
    return None


def has_pytest_django_settings(repo_dir):
    # True when pytest finds Django settings in the repo's pytest.ini, pyproject [tool.pytest.ini_options], setup.cfg
    # [tool:pytest], tox.ini [pytest] or conftest.py: DJANGO_SETTINGS_MODULE or the --ds option.
    sections = []
    for name in ("pytest.ini", "conftest.py"):
        if (repo_dir / name).is_file():
            sections.append((repo_dir / name).read_text())

    pyproject = repo_dir / "pyproject.toml"
    if pyproject.is_file():
        try:
            options = tomllib.loads(pyproject.read_text()).get("tool", {}).get("pytest", {}).get("ini_options", {})
        except tomllib.TOMLDecodeError:
            options = {}
        sections.append(str(options))

    for name, section in (("setup.cfg", "tool:pytest"), ("tox.ini", "pytest")):
        config_file = repo_dir / name
        if not config_file.is_file():
            continue

        parser = configparser.ConfigParser(interpolation=None, strict=False)
        with contextlib.suppress(configparser.Error):
            parser.read_string(config_file.read_text())
        if parser.has_section(section):
            sections.append(str(dict(parser[section])))

    return any(PYTEST_DJANGO_SETTINGS.search(text) for text in sections)


def project_python_runner(repo_dir):
    # The runner the repo's lock file or virtualenv names, or None when it names none.
    for lock_file, runner in PYTHON_RUNNERS:
        if (repo_dir / lock_file).is_file():
            return runner

    for venv in VENV_FOLDERS:
        if (repo_dir / venv / "bin/python").is_file():
            return [f"{venv}/bin/python", "-m"]
    return None


def django_test_label(test_path, manage_dir):
    # The dotted module of a test file, from the folder that holds manage.py.
    relative_path = pathlib.PurePosixPath(test_path).relative_to(manage_dir)
    return ".".join(relative_path.with_suffix("").parts)


def python_test_command(runner, test_paths, django_options, manage_script="manage.py"):
    # pytest on the changed test files, or, when django_options is a list, `<manage_script> test` on the dotted labels
    # of the ones under the manage script's folder, labels before options. A Django phase that names no test file
    # there gives no test command: `manage.py test` with no label runs the whole suite, which the gate refuses.
    if django_options is None:
        scope = " ".join(shlex.quote(p) for p in test_paths) or "{files:_test.py}"
        return f"{shlex.join([*runner, 'pytest'])} {scope}"

    manage_dir = pathlib.PurePosixPath(manage_script).parent
    labeled_paths = [path for path in test_paths if pathlib.PurePosixPath(path).is_relative_to(manage_dir)]
    if not labeled_paths:
        return None

    python_words = runner[:-1] if runner[-1:] == ["-m"] else [*runner, "python"]
    labels = [django_test_label(path, manage_dir) for path in labeled_paths]
    prompt_options = [] if NO_INPUT_OPTIONS & set(django_options) else ["--noinput"]
    return shlex.join([*python_words, manage_script, "test", *labels, *django_options, *prompt_options])


def python_commands(repo_dir, paths, listed_runner=None, listed_django=None, phase_lists_pytest=False, *,
                    derives_tests):
    # Tests run through the phase's listed runner, else the repo's lock file or virtualenv, else python3. Ruff runs
    # through the same runner, except a bare system python, where ruff is usually its own program. The tests are
    # `manage.py test` when the phase lists one, or when a manage.py sits at the root or above the phase's Python
    # files, no pytest-django settings sit beside it or at the root and the phase lists no pytest command; otherwise
    # pytest.
    python_paths = [p for p in paths if p.endswith(".py")]
    manage_script = nearest_manage_script(repo_dir, python_paths)
    has_config = any((repo_dir / name).is_file() for name in ("pyproject.toml", "pytest.ini", "setup.cfg", "manage.py"))
    if not python_paths or not (has_config or manage_script):
        return []

    django_options = None
    if listed_django:
        listed_runner, django_options, manage_script = listed_django
    elif not phase_lists_pytest and manage_script:
        manage_dir = (repo_dir / manage_script).parent
        if not has_pytest_django_settings(repo_dir) and not has_pytest_django_settings(manage_dir):
            django_options = []

    runner = listed_runner if listed_runner is not None else project_python_runner(repo_dir)
    if runner is None:
        runner = ["python3", "-m"]
    program_words = [word for word in runner if not ENV_ASSIGNMENT.match(word)]
    runs_system_python = program_words[:1] in (["python"], ["python3"])
    ruff_runner = [] if runs_system_python else runner

    commands = []
    pyproject = (repo_dir / "pyproject.toml")
    if pyproject.is_file() and "ruff" in pyproject.read_text():
        ruff_command = shlex.join([*ruff_runner, "ruff", "check"])
        commands.append(f"{ruff_command} {{files:.py}}")

    if not derives_tests:
        return commands

    test_file = DJANGO_TEST_FILE if django_options is not None else TEST_FILE
    test_paths = [p for p in python_paths if test_file.search(p)]
    test_command = python_test_command(runner, test_paths, django_options, manage_script)
    if test_command:
        commands.append(test_command)
    return commands


def cargo_test_scope(crate_dir, file_in_crate):
    # The cargo test arguments for one Rust file, given the crate directory and the file's path from it, or None when
    # no test belongs to it. `src/bin/<name>.rs` and every file under `src/bin/<name>/` are the binary `<name>`.
    # Any other file under `src/`, `lib.rs` and `main.rs` included, runs the library and binary unit tests
    # (`--lib --bins`) in a crate with a `src/lib.rs`, and the binaries (`--bins`) in a crate with none; `--lib` alone
    # would skip the unit tests in `main.rs` and in the modules only `main.rs` reaches. `tests/<name>.rs` is the test
    # target `<name>`. Any file under `tests/<dir>/` is the test target `<dir>` when `tests/<dir>/main.rs` exists, and
    # otherwise a helper that any integration test can include, so it runs every test target (`--tests`),
    # which already covers the library and every binary, so the crate's other test commands are dropped.
    # A `src/` change does not run the integration tests in `tests/`, because CI runs the full suite.
    # No module filter: a test in an unchanged module can pin the old behavior of the changed one, and the cost is
    # compiling the test binary, which a filter does not save.
    parts = pathlib.PurePosixPath(file_in_crate).with_suffix("").parts
    if len(parts) < 2:
        return None

    if parts[0] == "tests":
        if len(parts) == 2:
            return f"--test {parts[1]}"

        is_target_main_file = parts[2:] == ("main",)
        is_test_target_directory = is_target_main_file or (crate_dir / "tests" / parts[1] / "main.rs").is_file()
        return f"--test {parts[1]}" if is_test_target_directory else "--tests"

    if parts[0] != "src":
        return None

    is_under_bin_directory = parts[1] == "bin" and len(parts) > 2
    if is_under_bin_directory:
        return f"--bin {parts[2]}"

    if (crate_dir / "src" / "lib.rs").is_file():
        return "--lib --bins"
    return "--bins"


def cargo_commands(repo_dir, paths, derives_tests):
    commands_by_crate = {}
    for path in paths:
        is_rust_file = path.endswith(".rs")
        if not (is_rust_file or pathlib.PurePosixPath(path).name == "Cargo.toml"):
            continue

        crate_dir = nearest_directory_with(repo_dir, path, "Cargo.toml")
        if crate_dir is None:
            continue

        crate_commands = commands_by_crate.setdefault(crate_dir, [CARGO_CLIPPY])
        if not is_rust_file or not derives_tests:
            continue

        path_in_crate = str((repo_dir / path).relative_to(crate_dir))
        scope = cargo_test_scope(crate_dir, path_in_crate)
        test_command = f"cargo test {scope}" if scope else None
        if test_command and test_command not in crate_commands:
            crate_commands.append(test_command)

    commands = []
    for crate_dir, crate_commands in commands_by_crate.items():
        if "cargo test --tests" in crate_commands:
            crate_commands = [CARGO_CLIPPY, "cargo test --tests"]

        crate_rel = script_utils.directory_relative_to(repo_dir, crate_dir)
        commands += [in_directory(command, crate_rel) for command in crate_commands]
    return commands


def takes_listed_test_command(command, repo_dir):
    # A listed test command the gate can store: `coder_gate.py set` refuses one that runs a whole suite.
    return test_run_output.runs_tests(command) and not check_scope.runs_whole_check(command, str(repo_dir))


def runs_cargo(command):
    # True when a step of the command runs cargo once its wrappers are peeled: `cd crate && cargo test`,
    # `CARGO_BUILD_JOBS=4 cargo check`, `nice -n 19 env CARGO_BUILD_JOBS=4 cargo nextest run`. False for text the
    # shell splitter cannot read.
    try:
        simple_commands = split_simple_commands(command)
    except ValueError:
        return False

    for words in simple_commands:
        program_words = command_after_wrappers(words)
        if program_words and pathlib.PurePosixPath(program_words[0]).name == "cargo":
            return True
    return False


def test_command_families(command):
    # The runner families a listed test command runs: "js", "python" or "cargo", read from its text. A command that
    # names none of them, such as `make test-consistency` or `just test`, is the UNKNOWN_FAMILY.
    families = {family for family, runs_family in TEST_FAMILY_PATTERNS.items() if runs_family.search(command)}
    return families or {UNKNOWN_FAMILY}


def derive_gate_commands(repo_dir, phase_section):
    # The phase's listed test commands that run less than a whole suite are the gate's test commands, verbatim, and no
    # test command is derived. A phase that lists none of those gets the test commands derived from the files it names.
    paths = []
    for match in PATH_IN_BACKTICKS.finditer(phase_section):
        if match.group(1) not in paths:
            paths.append(match.group(1))

    by_package = {}
    for path in paths:
        package_dir = nearest_directory_with(repo_dir, path, "package.json")
        if package_dir is not None:
            by_package.setdefault(package_dir, []).append(path)

    listed = listed_commands(repo_dir, phase_section)
    listed_tests = [command for command in listed if takes_listed_test_command(command, repo_dir)]
    listed_families = set().union(*(test_command_families(command) for command in listed_tests))
    derives_js_tests = not listed_families & {"js", UNKNOWN_FAMILY}
    derives_python_tests = not listed_families & {"python", UNKNOWN_FAMILY}
    derives_cargo_tests = not listed_families & {"cargo", UNKNOWN_FAMILY}

    commands = []
    for package_dir, package_paths in by_package.items():
        commands += script_package_commands(repo_dir, package_dir, package_paths, derives_js_tests)
    root_manifests = BARE_CARGO_MANIFEST.findall(phase_section)
    listed_cargo = [command for command in listed if runs_cargo(command)]
    commands += listed_cargo or cargo_commands(repo_dir, paths + root_manifests, derives_cargo_tests)
    listed_runner = listed_python_runner(listed)
    listed_django = listed_django_test(listed)
    phase_lists_pytest = lists_pytest(listed)
    commands += python_commands(repo_dir, paths, listed_runner, listed_django, phase_lists_pytest,
                                derives_tests=derives_python_tests)
    commands += [command for command in listed_tests if command not in commands]
    return commands
