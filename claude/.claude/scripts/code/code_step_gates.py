"""Gate commands derived from a phase section: what to run for the files the phase names."""
import configparser
import contextlib
import json
import pathlib
import re
import shlex
import tomllib

import plan_format
import script_utils
from code_step_boundary import verification_command

CARGO_CLIPPY = "cargo clippy --all-targets -- -D warnings"
RUNS_CARGO = re.compile(r"(?:^|&&\s*)cargo\s")
TYPECHECK_SCRIPTS = ["typecheck", "type-check", "check-types", "tsc"]
SCRIPT_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mts", ".mjs")
TEST_SUFFIXES = ".test.ts,.test.tsx,.spec.ts,.spec.tsx,.test.js,.test.jsx"
TEST_FILE = re.compile(r"\.(test|spec)\.|(^|/)test_[^/]*\.py$|_test\.py$")
BARE_CARGO_MANIFEST = re.compile(r"`(Cargo\.toml)`")
PATH_IN_BACKTICKS = re.compile(r"`([\w.@-]+(?:/[\w.@\[\]()-]+)+\.\w+)(?::\d+(?:-\d+)?)?`")
PYTHON_RUNNERS = (("uv.lock", ["uv", "run"]), ("poetry.lock", ["poetry", "run"]), ("pdm.lock", ["pdm", "run"]),
                  ("Pipfile.lock", ["pipenv", "run"]))
VENV_DIRECTORIES = (".venv", "venv")
SHELL_OPERATORS = {"&&", "||", ";", "|", "&"}
DJANGO_TEST_FILE = re.compile(r"(^|/)test[^/]*\.py$")
PYTEST_DJANGO_SETTINGS = re.compile(r"DJANGO_SETTINGS_MODULE|--ds\b", re.IGNORECASE)
DJANGO_VALUE_OPTIONS = {"--settings", "--pythonpath", "-v", "--verbosity", "--parallel", "-k", "--tag", "--exclude-tag",
                        "-p", "--pattern", "-t", "--top-level-directory", "--testrunner"}
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def nearest_directory_with(repo_dir, rel_path, manifest_name):
    manifest = script_utils.nearest_file_upward((repo_dir / rel_path).parent, manifest_name, repo_dir)
    return manifest.parent if manifest else None


def in_directory(command, package_rel):
    return f"cd {shlex.quote(package_rel)} && {command}" if package_rel else command


def script_package_commands(repo_dir, package_dir, paths):
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

    test_paths = [p for p in relative_paths if TEST_FILE.search(p)]
    runner = "vitest run" if "vitest" in dependencies else "jest" if "jest" in dependencies else None
    if runner:
        scope = " ".join(shlex.quote(p) for p in test_paths) or "{files:" + TEST_SUFFIXES + "}"
        commands.append(in_directory(f"npx {runner} {scope}", package_rel))
    elif "test" in scripts:
        scope = " ".join(shlex.quote(p) for p in test_paths) or "{files:" + TEST_SUFFIXES + "}"
        commands.append(in_directory(f"npm test -- {scope}", package_rel))
    return commands


def listed_command_words(repo_dir, phase_section):
    # The words of each command the phase's Automated Verification lists, read the way the phase boundary reads them.
    for _, line in plan_format.automated_verification_rows(phase_section.splitlines()):
        if plan_format.runs_no_command(line):
            continue

        command = verification_command(line, repo_dir)
        if not command:
            continue

        try:
            yield shlex.split(command)
        except ValueError:
            continue


def chains_a_command(words):
    return any(word in SHELL_OPERATORS or word == "cd" for word in words)


def listed_python_runner(repo_dir, phase_section):
    # The words before `pytest` in the first pytest command the phase's Automated Verification lists, such as
    # ["uv", "run"] or ["DJANGO_SETTINGS_MODULE=app.test", ".venv/bin/python", "-m"], or None when it lists none. A
    # command that changes directory or chains another command before pytest gives no runner.
    for words in listed_command_words(repo_dir, phase_section):
        if "pytest" not in words:
            continue

        runner = words[:words.index("pytest")]
        if not chains_a_command(runner):
            return runner
    return None


def lists_pytest(repo_dir, phase_section):
    # True when any command the phase's Automated Verification lists runs pytest, with or without a usable runner.
    return any("pytest" in words for words in listed_command_words(repo_dir, phase_section))


def listed_django_test(repo_dir, phase_section):
    # (runner, options) of the first `<python> manage.py test` command the phase lists, or None when it lists none.
    # The runner is in the form of a pytest runner: ["uv", "run"] for `uv run python manage.py test`, and
    # ["python", "-m"] for a bare `python manage.py test`, so ruff runs through the same
    # words. The options are the flags after `test` ("--keepdb"); the listed test labels are dropped, because the gate
    # scopes the run to the changed test modules. A command that chains another command first gives none.
    for words in listed_command_words(repo_dir, phase_section):
        if "manage.py" not in words:
            continue

        manage_index = words.index("manage.py")
        is_test_command = words[manage_index + 1:manage_index + 2] == ["test"]
        runs_python = manage_index > 0 and pathlib.PurePosixPath(words[manage_index - 1]).name.startswith("python")
        if not (is_test_command and runs_python) or chains_a_command(words[:manage_index]):
            continue

        options = []
        after_test = words[manage_index + 2:]
        for position, word in enumerate(after_test):
            follows_value_option = position and after_test[position - 1] in DJANGO_VALUE_OPTIONS
            if word.startswith("-") or follows_value_option:
                options.append(word)
        launcher = words[:manage_index - 1]
        return [*launcher, words[manage_index - 1], "-m"], options
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

    for venv in VENV_DIRECTORIES:
        if (repo_dir / venv / "bin/python").is_file():
            return [f"{venv}/bin/python", "-m"]
    return None


def django_test_label(test_path):
    return ".".join(pathlib.PurePosixPath(test_path).with_suffix("").parts)


def python_test_command(runner, test_paths, django_options):
    # pytest on the changed test files, or, when django_options is a list, `manage.py test` on their dotted labels.
    # A Django phase that names no test file gives no test command: `manage.py test` with no label runs the whole
    # suite, which the gate refuses.
    if django_options is None:
        scope = " ".join(shlex.quote(p) for p in test_paths) or "{files:_test.py}"
        return f"{shlex.join([*runner, 'pytest'])} {scope}"

    if not test_paths:
        return None

    python_words = runner[:-1] if runner[-1:] == ["-m"] else [*runner, "python"]
    labels = [django_test_label(path) for path in test_paths]
    return shlex.join([*python_words, "manage.py", "test", *labels, *django_options])


def python_commands(repo_dir, paths, listed_runner=None, listed_django=None, phase_lists_pytest=False):
    # Tests run through the phase's listed runner, else the repo's lock file or virtualenv, else python3. Ruff runs
    # through the same runner, except a bare system python, where ruff is usually its own program. The tests are
    # `manage.py test` when the phase lists it, or when the repo has a manage.py and no pytest-django settings and the
    # phase lists no pytest command; otherwise pytest.
    python_paths = [p for p in paths if p.endswith(".py")]
    has_config = any((repo_dir / name).is_file() for name in ("pyproject.toml", "pytest.ini", "setup.cfg", "manage.py"))
    if not python_paths or not has_config:
        return []

    django_options = None
    if listed_django:
        listed_runner, django_options = listed_django
    elif not phase_lists_pytest and (repo_dir / "manage.py").is_file() and not has_pytest_django_settings(repo_dir):
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

    test_file = DJANGO_TEST_FILE if django_options is not None else TEST_FILE
    test_paths = [p for p in python_paths if test_file.search(p)]
    test_command = python_test_command(runner, test_paths, django_options)
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


def cargo_commands(repo_dir, paths):
    commands_by_crate = {}
    for path in paths:
        is_rust_file = path.endswith(".rs")
        if not (is_rust_file or pathlib.PurePosixPath(path).name == "Cargo.toml"):
            continue

        crate_dir = nearest_directory_with(repo_dir, path, "Cargo.toml")
        if crate_dir is None:
            continue

        crate_commands = commands_by_crate.setdefault(crate_dir, [CARGO_CLIPPY])
        if not is_rust_file:
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


def listed_cargo_commands(repo_dir, phase_section):
    # The cargo commands the phase's Automated Verification lists, read the way the phase boundary reads them.
    listed = []
    for _, line in plan_format.automated_verification_rows(phase_section.splitlines()):
        if plan_format.runs_no_command(line):
            continue

        command = verification_command(line, repo_dir)
        if not command:
            continue

        command_without_env = script_utils.without_leading_env_assignments(command)
        if RUNS_CARGO.search(command_without_env) and command not in listed:
            listed.append(command)
    return listed


def derive_gate_commands(repo_dir, phase_section):
    paths = []
    for match in PATH_IN_BACKTICKS.finditer(phase_section):
        if match.group(1) not in paths:
            paths.append(match.group(1))

    by_package = {}
    for path in paths:
        package_dir = nearest_directory_with(repo_dir, path, "package.json")
        if package_dir is not None:
            by_package.setdefault(package_dir, []).append(path)

    commands = []
    for package_dir, package_paths in by_package.items():
        commands += script_package_commands(repo_dir, package_dir, package_paths)
    root_manifests = BARE_CARGO_MANIFEST.findall(phase_section)
    listed_cargo = listed_cargo_commands(repo_dir, phase_section)
    commands += listed_cargo or cargo_commands(repo_dir, paths + root_manifests)
    listed_runner = listed_python_runner(repo_dir, phase_section)
    listed_django = listed_django_test(repo_dir, phase_section)
    phase_lists_pytest = lists_pytest(repo_dir, phase_section)
    commands += python_commands(repo_dir, paths, listed_runner, listed_django, phase_lists_pytest)
    return commands
