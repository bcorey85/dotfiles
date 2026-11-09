"""Tests for gate_commands.py: the commands derived from the files and Automated Verification items of a phase."""
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
module_spec = importlib.util.spec_from_file_location("gate_commands", toolkit_paths.CODE_DIR / "gate_commands.py")
gate_commands = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(gate_commands)
coder_gate_spec = importlib.util.spec_from_file_location("coder_gate", toolkit_paths.CODE_DIR / "coder_gate.py")
coder_gate = importlib.util.module_from_spec(coder_gate_spec)
coder_gate_spec.loader.exec_module(coder_gate)

RUFF_CONFIG = "[tool.ruff]\n"
BACKEND_FILES = "**File**: `backend/app/models.py`\n**File**: `backend/app/tests/test_models.py`\n"
CLIPPY = "cargo clippy --all-targets -- -D warnings"


def django_phase(verification=""):
    phase = "**File**: `app/models.py`\n**File**: `app/tests/test_models.py`\n"
    if verification:
        phase += f"\n#### Automated Verification:\n\n- [ ] **Tests**: models pass - `{verification}`\n"
    return phase


class GateCommandsTestCase(unittest.TestCase):
    def new_repo(self, repo_files):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        repo = pathlib.Path(folder.name)
        for name, text in repo_files.items():
            (repo / name).parent.mkdir(parents=True, exist_ok=True)
            (repo / name).write_text(text)
        return repo


class PythonCommandsTest(GateCommandsTestCase):
    def test_python_gate_commands_follow_the_runner_and_test_command_the_repo_and_phase_name(self):
        cases = [
            ("a listed pytest command gives its runner to ruff and the gate",
             {"pyproject.toml": RUFF_CONFIG, "uv.lock": ""},
             "**File**: `app/models.py`\n**File**: `tests/test_models.py`\n\n#### Automated Verification:\n\n"
             "- [ ] **Tests**: models pass - `DJANGO_SETTINGS_MODULE=app.test poetry run pytest tests/`\n",
             ["DJANGO_SETTINGS_MODULE=app.test poetry run ruff check {files:.py}",
              "DJANGO_SETTINGS_MODULE=app.test poetry run pytest tests/"]),
            ("a listed pytest command with no path is replaced by the derived scoped run",
             {"pyproject.toml": RUFF_CONFIG, "uv.lock": ""},
             "**File**: `app/models.py`\n**File**: `tests/test_models.py`\n\n#### Automated Verification:\n\n"
             "- [ ] **Tests**: models pass - `poetry run pytest`\n",
             ["poetry run ruff check {files:.py}", "poetry run pytest tests/test_models.py"]),
            ("a django repo without pytest django settings runs manage.py test on dotted labels",
             {"manage.py": "", "pyproject.toml": "[tool.ruff]\n[tool.pytest.ini_options]\naddopts = '-q'\n"},
             django_phase(),
             ["ruff check {files:.py}", "python3 manage.py test app.tests.test_models --noinput"]),
            ("a django repo runs manage.py test through the runner the lock file names",
             {"manage.py": "", "pyproject.toml": "", "uv.lock": ""},
             django_phase(),
             ["uv run python manage.py test app.tests.test_models --noinput"]),
            ("a listed whole-suite manage.py test runs on the changed test modules with its runner and options",
             {"manage.py": "", "pyproject.toml": RUFF_CONFIG, "uv.lock": ""},
             django_phase("DJANGO_SETTINGS_MODULE=app.test poetry run python manage.py test --keepdb"),
             ["DJANGO_SETTINGS_MODULE=app.test poetry run python -m ruff check {files:.py}",
              "DJANGO_SETTINGS_MODULE=app.test poetry run python manage.py test app.tests.test_models --keepdb "
              "--noinput"]),
            ("a django phase that names no test file runs no test command",
             {"manage.py": "", "pyproject.toml": RUFF_CONFIG},
             "**File**: `app/models.py`\n",
             ["ruff check {files:.py}"]),
            ("a listed pytest command that changes directory gives no runner to ruff",
             {"pyproject.toml": RUFF_CONFIG, "uv.lock": ""},
             "**File**: `app/models.py`\n\n#### Automated Verification:\n\n"
             "- [ ] **Tests**: models pass - `cd api && poetry run pytest tests/`\n",
             ["uv run ruff check {files:.py}", "cd api && poetry run pytest tests/"]),
            ("a manage.py in the subfolder above the phase files runs manage.py test from there",
             {"backend/manage.py": ""},
             BACKEND_FILES,
             ["cd backend && npm run typecheck", "python3 backend/manage.py test app.tests.test_models --noinput"]),
            ("a listed system python runner keeps ruff as its own program",
             {"pyproject.toml": RUFF_CONFIG},
             "**File**: `tests/test_models.py`\n\n#### Automated Verification:\n\n"
             "- [ ] **Tests**: models pass - `python -m pytest tests/`\n",
             ["ruff check {files:.py}", "python -m pytest tests/"]),
        ]

        for label, repo_files, phase, expected in cases:
            with self.subTest(label):
                repo = self.new_repo(repo_files)
                if label.startswith("a manage.py in the subfolder"):
                    (repo / "backend/package.json").write_text('{"scripts": {"typecheck": "tsc"}}')

                self.assertEqual(expected, gate_commands.derive_gate_commands(repo, phase))

    def test_a_django_repo_with_pytest_django_settings_keeps_pytest(self):
        settings_files = {
            "pytest.ini": "[pytest]\nDJANGO_SETTINGS_MODULE = app.settings\n",
            "setup.cfg": "[tool:pytest]\nDJANGO_SETTINGS_MODULE = app.settings\n",
            "conftest.py": "import os\nos.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')\n",
        }
        for name, text in settings_files.items():
            with self.subTest(name=name):
                repo = self.new_repo({"manage.py": "", "pyproject.toml": "", name: text})

                commands = gate_commands.derive_gate_commands(repo, django_phase())

                self.assertEqual(["python3 -m pytest app/tests/test_models.py"], commands)

    def test_a_listed_test_command_the_gate_would_refuse_is_not_taken(self):
        repo = self.new_repo({"pkg/package.json": '{"devDependencies": {"vitest": "1"}}', "pkg/src/.keep": ""})
        phase = ("**File**: `pkg/src/a.test.ts`\n\n#### Automated Verification:\n\n"
                 "- [ ] **Tests**: all pass - `npm test`\n")

        self.assertEqual(["cd pkg && npx vitest run src/a.test.ts"], gate_commands.derive_gate_commands(repo, phase))

    def test_a_listed_make_target_replaces_the_derived_vitest_command(self):
        repo = self.new_repo({"pkg/package.json": '{"devDependencies": {"vitest": "1"}}', "pkg/src/.keep": ""})
        phase = ("**File**: `pkg/src/a.consistency.test.ts`\n\n#### Automated Verification:\n\n"
                 "- [ ] **Tests**: consistency - `make test-consistency ARGS=\"src/a.consistency.test.ts\"`\n")

        self.assertEqual(['make test-consistency ARGS="src/a.consistency.test.ts"'],
                         gate_commands.derive_gate_commands(repo, phase))


class CargoCommandsTest(GateCommandsTestCase):
    def test_cargo_tests_are_the_test_target_binary_or_library_of_each_named_rust_file(self):
        repo = self.new_repo({"crate/Cargo.toml": '[package]\nname = "crate"\n', "crate/src/lib.rs": "",
                              "crate/tests/side_streams/main.rs": "", "crate/tests/common/.keep": ""})
        cases = {
            "crate/tests/side_streams.rs": "cargo test --test side_streams",
            "crate/tests/side_streams/helper.rs": "cargo test --test side_streams",
            "crate/tests/common/mod.rs": "cargo test --tests",
            "crate/src/a/b.rs": "cargo test --lib --bins",
            "crate/src/bin/tool.rs": "cargo test --bin tool",
            "crate/benches/speed.rs": None,
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                wanted = [f"cd crate && {CLIPPY}"] + ([f"cd crate && {expected}"] if expected else [])

                self.assertEqual(wanted, gate_commands.cargo_commands(repo, [path], derives_tests=True))

    def test_a_phase_that_lists_cargo_test_without_clippy_gets_a_scoped_clippy_first(self):
        repo = self.new_repo({"Cargo.toml": '[package]\nname = "root"\n', "src/lib.rs": ""})
        phase = ("**File**: `src/a.rs`\n\n#### Automated Verification:\n\n"
                 "- [ ] **Tests**: unit - `cargo test --lib`\n")

        commands = gate_commands.derive_gate_commands(repo, phase)

        self.assertEqual(["cargo clippy --lib --bins --tests -- -D warnings", "cargo test --lib"], commands)

    def helper_phase_commands(self, verification_line):
        repo = self.new_repo({"crate/Cargo.toml": '[package]\nname = "crate"\n', "crate/src/lib.rs": "",
                              "crate/tests/common/mod.rs": ""})
        phase = f"**File**: `crate/tests/common/mod.rs`\n\n#### Automated Verification:\n\n{verification_line}\n"
        return gate_commands.derive_gate_commands(repo, phase)

    def test_listed_cargo_commands_behind_wrappers_and_after_a_cd_are_taken(self):
        nextest = "nice -n 19 env CARGO_BUILD_JOBS=4 cargo nextest run --lib -E 'test(orders_total)'"
        check = "taskset -c 0-5 nice -n 19 env CARGO_BUILD_JOBS=4 cargo check --all-targets"
        after_cd = "cd crate && cargo test --test orders"
        cases = [
            ("wrappers", f"- [ ] Orders total passes: `{nextest}`\n- [ ] Crate builds: `{check}`",
             ["cd crate && cargo clippy --tests -- -D warnings", nextest, check]),
            ("cd", f"- [ ] Orders test passes: `{after_cd}`",
             ["cd crate && cargo clippy --tests -- -D warnings", after_cd]),
        ]
        for label, verification_line, expected in cases:
            with self.subTest(label):
                commands = self.helper_phase_commands(verification_line)

                self.assertEqual(expected, [command for command in commands if "cargo" in command])

    def test_derived_cargo_commands_are_kept_when_the_listed_command_lists_no_cargo_run(self):
        listed = {
            "a grep for a todo": "git grep -n TODO -- crate/src",
            "a grep that only names cargo": "git grep -n cargo -- crate/src",
        }
        for label, command in listed.items():
            with self.subTest(label):
                commands = self.helper_phase_commands(f"- [ ] No stray text: `{command}`")

                self.assertIn("cd crate && cargo test --tests", commands)
                self.assertIn("cd crate && cargo clippy --all-targets -- -D warnings", commands)

    def test_cargo_commands_are_merged_per_crate_without_duplicates_and_never_run_a_whole_crate(self):
        repo_files = {}
        for crate in ("one", "two"):
            repo_files[f"{crate}/src/lib.rs"] = ""
            repo_files[f"{crate}/Cargo.toml"] = f'[package]\nname = "{crate}"\n'
        repo = self.new_repo(repo_files)
        paths = ["one/src/a.rs", "two/src/b.rs", "one/src/a.rs", "one/src/lib.rs", "one/Cargo.toml", "one/src/c.rs"]

        commands = gate_commands.cargo_commands(repo, paths, derives_tests=True)

        self.assertEqual([f"cd one && {CLIPPY}", "cd one && cargo test --lib --bins",
                          f"cd two && {CLIPPY}", "cd two && cargo test --lib --bins"], commands)

    def test_a_shared_test_helper_change_runs_only_clippy_and_the_all_targets_test(self):
        repo = self.new_repo({"crate/Cargo.toml": '[package]\nname = "crate"\n', "crate/src/lib.rs": "",
                              "crate/tests/common/mod.rs": ""})
        paths = ["crate/tests/side_streams.rs", "crate/src/a.rs", "crate/tests/common/mod.rs", "crate/src/bin/tool.rs",
                 "crate/tests/orders.rs"]

        commands = gate_commands.cargo_commands(repo, paths, derives_tests=True)

        self.assertEqual([f"cd crate && {CLIPPY}", "cd crate && cargo test --tests"], commands)

    def test_a_crate_with_no_library_runs_every_file_under_src_with_bins_once(self):
        repo = self.new_repo({"tool/src/store/.keep": "", "tool/src/main.rs": "",
                              "tool/Cargo.toml": '[package]\nname = "tool"\n'})
        paths = ["tool/src/store/query.rs", "tool/src/store/mod.rs", "tool/src/main.rs"]

        commands = gate_commands.cargo_commands(repo, paths, derives_tests=True)

        self.assertEqual([f"cd tool && {CLIPPY}", "cd tool && cargo test --bins"], commands)

    def test_a_manifest_alone_or_a_file_outside_src_and_tests_gives_clippy_and_no_test(self):
        repo = self.new_repo({"Cargo.toml": '[package]\nname = "root-crate"\n', "src/.keep": ""})

        commands = gate_commands.cargo_commands(repo, ["Cargo.toml", "benches/speed.rs", "build.rs"],
                                                derives_tests=True)

        self.assertEqual([CLIPPY], commands)

    def test_scoped_clippy_lints_examples_benches_and_build_scripts_as_their_own_targets(self):
        repo = self.new_repo({"crate/Cargo.toml": '[package]\nname = "crate"\n', "crate/src/lib.rs": ""})
        cases = [
            ("a changed example and an example folder",
             ["crate/examples/demo.rs", "crate/examples/wide/main.rs"],
             "cd crate && cargo clippy --example demo --example wide -- -D warnings"),
            ("a helper folder of examples and benches",
             ["crate/examples/common/helpers.rs", "crate/benches/common/helpers.rs"],
             "cd crate && cargo clippy --examples --benches -- -D warnings"),
            ("a build script", ["crate/build.rs"], "cd crate && cargo clippy --lib --bins --tests -- -D warnings"),
        ]
        for name, paths, expected in cases:
            with self.subTest(name):
                self.assertEqual([expected], gate_commands.scoped_clippy_commands(repo, paths))

    def test_scoped_clippy_merges_the_targets_of_one_crate_into_one_run(self):
        repo = self.new_repo({"crate/Cargo.toml": '[package]\nname = "crate"\n', "crate/src/lib.rs": "",
                              "tool/Cargo.toml": '[package]\nname = "tool"\n'})
        paths = ["crate/tests/orders.rs", "crate/src/a.rs", "crate/tests/orders.rs", "crate/src/b.rs",
                 "crate/tests/side_streams.rs", "crate/src/bin/tool.rs", "tool/Cargo.toml", "notes.md"]

        commands = gate_commands.scoped_clippy_commands(repo, paths)

        self.assertEqual(["cd crate && cargo clippy --test orders --lib --bins --tests --test side_streams --bin tool"
                          " -- -D warnings",
                          "cd tool && cargo clippy --bins --tests -- -D warnings"], commands)

    def test_a_phase_that_lists_its_own_clippy_gets_no_derived_clippy(self):
        repo = self.new_repo({"crate/Cargo.toml": '[package]\nname = "crate"\n', "crate/src/lib.rs": ""})
        phase = ("**File**: `crate/tests/orders.rs`\n\n#### Automated Verification:\n\n"
                 "- [ ] Orders lints clean: `cargo clippy --test orders -- -D warnings`\n"
                 "- [ ] Orders test passes: `cargo test --test orders`\n")

        commands = gate_commands.derive_gate_commands(repo, phase)

        self.assertEqual(["cargo clippy --test orders -- -D warnings", "cargo test --test orders"], commands)

    def test_a_quoted_cargo_clippy_in_a_listed_command_still_gets_the_scoped_clippy(self):
        repo = self.new_repo({"crate/Cargo.toml": '[package]\nname = "crate"\n', "crate/src/lib.rs": ""})
        phase = ("**File**: `crate/tests/orders.rs`\n\n#### Automated Verification:\n\n"
                 "- [ ] Orders test passes: `cargo test --test orders -- 'cargo clippy'`\n")

        commands = gate_commands.derive_gate_commands(repo, phase)

        self.assertIn("cd crate && cargo clippy --test orders -- -D warnings", commands)


class ScriptPackageCommandsTest(GateCommandsTestCase):
    def test_a_tsconfig_with_no_typecheck_script_runs_tsc_and_a_lint_script_runs_eslint(self):
        repo = self.new_repo({
            "pkg/package.json": json.dumps({"scripts": {"lint": "eslint ."}, "devDependencies": {"vitest": "1"}}),
            "pkg/tsconfig.json": "{}",
        })
        phase = "**File**: `pkg/src/a.ts`\n"

        commands = gate_commands.derive_gate_commands(repo, phase)

        self.assertEqual(["cd pkg && npx tsc --noEmit", "cd pkg && npx eslint {files:.ts}"], commands[:2])


ROOT_AND_NESTED_FILES = {"pyproject.toml": RUFF_CONFIG, "app.py": "", "test_app.py": "", "pkg/b.py": "",
                         "tests/test_b.py": ""}


class RootFilesTest(GateCommandsTestCase):
    def test_a_phase_that_names_repo_root_files_gets_the_gate_a_nested_phase_gets(self):
        repo = self.new_repo(ROOT_AND_NESTED_FILES)

        root = gate_commands.derive_gate_commands(repo, "- `app.py`\n- `test_app.py`\n")
        nested = gate_commands.derive_gate_commands(repo, "- `pkg/b.py`\n- `tests/test_b.py`\n")

        self.assertEqual(["ruff check {files:.py}", "python3 -m pytest test_app.py"], root)
        self.assertEqual(["ruff check {files:.py}", "python3 -m pytest tests/test_b.py"], nested)

    def test_a_bare_dotted_name_that_is_no_repo_root_file_adds_no_command(self):
        repo = self.new_repo(ROOT_AND_NESTED_FILES)

        commands = gate_commands.derive_gate_commands(repo, "Use `os.path` on `row.ts` and `test_gone.py`.\n")

        self.assertEqual([], commands)

    def test_a_sveltekit_route_path_with_a_plus_is_a_path(self):
        repo = self.new_repo({})

        paths = gate_commands.plan_format.named_paths("**File**: `src/routes/+page.svelte`\n", repo)

        self.assertEqual(["src/routes/+page.svelte"], paths)


class GateCommandsCliTest(GateCommandsTestCase):
    def run_cli(self, repo, *args):
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        return subprocess.run([sys.executable, str(toolkit_paths.CODE_DIR / "gate_commands.py"), *args], cwd=repo,
                              capture_output=True, text=True, check=False)

    def test_the_plan_phase_prints_one_gate_command_per_line(self):
        repo = self.new_repo({
            "pyproject.toml": RUFF_CONFIG,
            "docs/plans/p/spec.md": "## Phase 1: First\n\n**File**: `app/models.py`\n",
        })

        done = self.run_cli(repo, "docs/plans/p/spec.md", "1")

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(["ruff check {files:.py}", "python3 -m pytest {tests:.py}"], done.stdout.splitlines())

    def test_one_phase_leaves_out_the_test_files_of_another_phase(self):
        repo = self.new_repo({
            "pyproject.toml": RUFF_CONFIG,
            "docs/plans/p/spec.md": ("## Phase 1: First\n\n**File**: `app/models.py`\n\n"
                                     "## Phase 2: Second\n\n**File**: `tests/test_two.py`\n"),
        })

        first = self.run_cli(repo, "docs/plans/p/spec.md", "1")
        second = self.run_cli(repo, "docs/plans/p/spec.md", "2")

        self.assertIn("python3 -m pytest {tests:.py}", first.stdout.splitlines())
        self.assertNotIn("tests/test_two.py", first.stdout)
        self.assertIn("python3 -m pytest tests/test_two.py", second.stdout.splitlines())

    def test_a_repo_with_a_commit_gets_the_readability_check_against_head(self):
        repo = self.new_repo({"pyproject.toml": RUFF_CONFIG})
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q",
                        "--allow-empty", "-m", "base"], cwd=repo, check=True)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True,
                              check=True).stdout.strip()

        done = self.run_cli(repo, "-", "1")

        self.assertEqual(done.returncode, 0, done.stderr)
        expected = f"python3 {toolkit_paths.CODE_DIR / 'readability_check.py'} --base {head}"
        self.assertEqual([expected], done.stdout.splitlines())

    def test_a_dash_for_the_plan_prints_no_command(self):
        repo = self.new_repo({"pyproject.toml": RUFF_CONFIG})

        done = self.run_cli(repo, "-", "1")

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual("", done.stdout.strip())


class PythonRunnerTest(GateCommandsTestCase):
    def test_python_commands_run_through_the_virtualenv_python(self):
        repo = self.new_repo({"pyproject.toml": RUFF_CONFIG, ".venv/bin/python": ""})

        commands = gate_commands.python_commands(repo, ["app/a.py", "tests/test_a.py"], derives_tests=True)

        self.assertEqual([".venv/bin/python -m ruff check {files:.py}", ".venv/bin/python -m pytest tests/test_a.py"],
                         commands)

    def test_a_listed_manage_py_test_option_keeps_its_value_and_the_labels_go_before_the_options(self):
        cases = {
            "python manage.py test --settings app.test":
                "python manage.py test app.tests.test_models --settings app.test --noinput",
            "python manage.py test --parallel": "python manage.py test app.tests.test_models --parallel --noinput",
            "python manage.py test --no-input": "python manage.py test app.tests.test_models --no-input",
        }
        for listed, expected in cases.items():
            with self.subTest(listed=listed):
                repo = self.new_repo({"manage.py": ""})

                self.assertEqual([expected], gate_commands.derive_gate_commands(repo, django_phase(listed)))

    def test_a_listed_manage_py_test_that_excludes_a_tag_is_taken_verbatim(self):
        for listed in ("python manage.py test --exclude-tag slow", "python manage.py test --exclude-tag=slow"):
            with self.subTest(listed=listed):
                repo = self.new_repo({"manage.py": ""})

                self.assertEqual([listed], gate_commands.derive_gate_commands(repo, django_phase(listed)))

    def test_a_phase_that_lists_a_whole_suite_pytest_keeps_pytest_in_a_django_repo(self):
        for listed, expected in (("python -m pytest", "python -m pytest app/tests/test_models.py"),
                                 ("cd app && pytest", "python3 -m pytest app/tests/test_models.py")):
            with self.subTest(listed=listed):
                repo = self.new_repo({"manage.py": "", "pyproject.toml": ""})

                self.assertEqual([expected], gate_commands.derive_gate_commands(repo, django_phase(listed)))

    def test_a_listed_test_command_that_changes_directory_is_taken_verbatim(self):
        repo = self.new_repo({"pyproject.toml": "", "poetry.lock": ""})
        phase = ("**File**: `backend/app/tests/test_models.py`\n\n#### Automated Verification:\n\n"
                 "- [ ] **Tests**: models pass - `cd backend && poetry run python manage.py test app.tests`\n")

        commands = gate_commands.derive_gate_commands(repo, phase)

        self.assertIn("cd backend && poetry run python manage.py test app.tests", commands)
        self.assertEqual([], [command for command in commands if "pytest" in command or "vitest" in command])

    def test_a_django_phase_runs_the_tests_module_it_names(self):
        repo = self.new_repo({"manage.py": ""})
        phase = ("**File**: `app/models.py`\n**File**: `app/tests.py`\n**File**: `app/tests_views.py`\n"
                 "**File**: `app/orders_test.py`\n")

        commands = gate_commands.derive_gate_commands(repo, phase)

        self.assertIn("python3 manage.py test app.tests app.tests_views --noinput", commands)


class CoderTestFilesTest(GateCommandsTestCase):
    # A phase that names no test file gets a command with a {tests:...} placeholder; the gate fills it with the test
    # files the coder created.
    def filled_command(self, repo_files, phase, marker):
        repo = self.new_repo(repo_files)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        commands = gate_commands.derive_gate_commands(repo, phase)
        test_command = next(command for command in commands if marker in command)
        return coder_gate.fill_files(test_command, str(repo))

    def test_a_vitest_phase_naming_no_test_file_runs_every_test_file_the_coder_creates(self):
        names = ("src/existing.ts", "src/foo.spec.js", "src/foo.test.mts", "src/__tests__/foo.jsx", "src/helper.js")
        repo_files = {f"backend/{name}": "export {}\n" for name in names}
        repo_files["backend/package.json"] = '{"devDependencies": {"vitest": "1"}}'

        filled = self.filled_command(repo_files, "**File**: `backend/src/existing.ts`\n", "vitest")

        self.assertEqual("cd backend && npx vitest run src/foo.spec.js src/foo.test.mts", filled)

    def test_a_jest_phase_naming_no_test_file_also_runs_the_script_files_under_tests(self):
        names = ("src/a.ts", "src/foo.spec.js", "src/__tests__/foo.jsx", "src/helper.js")
        repo_files = {f"pkg/{name}": "export {}\n" for name in names}
        repo_files["pkg/package.json"] = '{"devDependencies": {"jest": "29"}}'

        filled = self.filled_command(repo_files, "**File**: `pkg/src/a.ts`\n", "jest")

        self.assertEqual("cd pkg && npx jest src/__tests__/foo.jsx src/foo.spec.js", filled)

    def test_an_npm_test_script_that_wraps_jest_also_runs_the_script_files_under_tests(self):
        expected = {
            "react-scripts test": "cd pkg && npm test -- src/__tests__/foo.js src/foo.spec.js",
            "jest --ci": "cd pkg && npm test -- src/__tests__/foo.js src/foo.spec.js",
            "mocha": "cd pkg && npm test -- src/foo.spec.js",
        }
        for test_script, wanted in expected.items():
            with self.subTest(test_script=test_script):
                repo_files = {f"pkg/{name}": "export {}\n" for name in ("src/a.js", "src/foo.spec.js",
                                                                          "src/__tests__/foo.js")}
                repo_files["pkg/package.json"] = json.dumps({"scripts": {"test": test_script}})

                filled = self.filled_command(repo_files, "**File**: `pkg/src/a.js`\n", "npm test")

                self.assertEqual(wanted, filled)

    def test_a_python_phase_naming_no_test_file_runs_every_test_file_the_coder_creates(self):
        names = ("app/models.py", "app/test_models.py", "app/orders_test.py", "app/conf.py", "tests/__init__.py",
                 "tests/conftest.py")
        repo_files = dict.fromkeys(names, "")
        repo_files["pyproject.toml"] = ""

        filled = self.filled_command(repo_files, "**File**: `app/models.py`\n", "pytest")

        self.assertEqual("python3 -m pytest app/orders_test.py app/test_models.py", filled)


if __name__ == "__main__":
    unittest.main()
