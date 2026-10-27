"""Gate commands derived from a phase section: what to run for the files the phase names."""
import json
import pathlib
import re
import shlex

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


def python_commands(repo_dir, paths):
    python_paths = [p for p in paths if p.endswith(".py")]
    if not python_paths or not any(
        (repo_dir / name).is_file() for name in ("pyproject.toml", "pytest.ini", "setup.cfg")
    ):
        return []
    commands = []
    pyproject = (repo_dir / "pyproject.toml")
    if pyproject.is_file() and "ruff" in pyproject.read_text():
        commands.append("ruff check {files:.py}")
    test_paths = [p for p in python_paths if TEST_FILE.search(p)]
    scope = " ".join(shlex.quote(p) for p in test_paths) or "{files:_test.py}"
    commands.append(f"python3 -m pytest {scope}")
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
    commands += python_commands(repo_dir, paths)
    return commands
