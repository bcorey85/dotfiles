"""Gate commands derived from a phase section: what to run for the files the phase names."""
import json
import pathlib
import re
import shlex

import check_scope
import plan_format
import script_utils
import test_run_output
from code_step_boundary import verification_command

CARGO_CLIPPY = "cargo clippy --all-targets -- -D warnings"
RUNS_CARGO = re.compile(r"(?:^|&&\s*)cargo\s")
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
VENV_DIRECTORIES = (".venv", "venv")
SHELL_OPERATORS = {"&&", "||", ";", "|", "&"}
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


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


def listed_python_runner(listed):
    # The words before `pytest` in the first listed pytest command, such as ["uv", "run"] or
    # ["DJANGO_SETTINGS_MODULE=app.test", ".venv/bin/python", "-m"], or None when it lists none. A command that
    # changes directory or chains another command before pytest gives no runner.
    for command in listed:
        try:
            words = shlex.split(command)
        except ValueError:
            continue
        if "pytest" not in words:
            continue

        runner = words[:words.index("pytest")]
        chains_a_command = any(word in SHELL_OPERATORS or word == "cd" for word in runner)
        if not chains_a_command:
            return runner
    return None


def project_python_runner(repo_dir):
    # The runner the repo's lock file or virtualenv names, or None when it names none.
    for lock_file, runner in PYTHON_RUNNERS:
        if (repo_dir / lock_file).is_file():
            return runner

    for venv in VENV_DIRECTORIES:
        if (repo_dir / venv / "bin/python").is_file():
            return [f"{venv}/bin/python", "-m"]
    return None


def python_commands(repo_dir, paths, listed_runner=None, *, derives_tests):
    # Tests run through the phase's listed pytest runner, else the repo's lock file or virtualenv, else python3. Ruff
    # runs through the same runner, except a bare system python, where ruff is usually its own program.
    python_paths = [p for p in paths if p.endswith(".py")]
    if not python_paths or not any(
        (repo_dir / name).is_file() for name in ("pyproject.toml", "pytest.ini", "setup.cfg")
    ):
        return []

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

    test_paths = [p for p in python_paths if TEST_FILE.search(p)]
    scope = " ".join(shlex.quote(p) for p in test_paths) or "{files:_test.py}"
    pytest_command = shlex.join([*runner, "pytest"])
    commands.append(f"{pytest_command} {scope}")
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
    listed_cargo = [command for command in listed
                    if RUNS_CARGO.search(script_utils.without_leading_env_assignments(command))]
    commands += listed_cargo or cargo_commands(repo_dir, paths + root_manifests, derives_cargo_tests)
    commands += python_commands(repo_dir, paths, listed_python_runner(listed), derives_tests=derives_python_tests)
    commands += [command for command in listed_tests if command not in commands]
    return commands
