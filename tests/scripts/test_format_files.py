"""Checks for format_files.py, the shared autofix formatter runner of the format hook and the review loop.

Formatters are fake executables on PATH; the hook's own tests cover the web tool choice."""
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import format_files
import script_utils

FAKE_RUFF = """#!/bin/sh
echo "$@" >> {calls}
[ "$1" = format ] || exit 0
shift
for f in "$@"; do echo '# formatted' >> "$f"; done
"""

# A real repo that runs ruff only through astral-sh/ruff-pre-commit: no ruff config file.
TLDR_PRE_COMMIT_CONFIG = """repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.11
    hooks:
      - id: ruff
        files: ^backend/
      - id: ruff-format
        files: ^backend/
  - repo: local
    hooks:
      - id: mypy
        name: mypy
        entry: uv run --directory backend mypy .
        language: system
        types: [python]
        files: ^backend/
        pass_filenames: false
      - id: eslint
        name: eslint
        entry: pnpm --dir frontend lint
        language: system
        files: ^frontend/
        pass_filenames: false
      - id: prettier
        name: prettier
        entry: pnpm --dir frontend format:check
        language: system
        files: ^frontend/
        pass_filenames: false
"""


class RunFormattersTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.repo = pathlib.Path(scratch.name) / "repo"
        self.repo.mkdir()
        self.bin = pathlib.Path(scratch.name) / "bin"
        self.bin.mkdir()
        # Only the fake tools on PATH, so no real formatter runs.
        patcher = mock.patch.dict(os.environ, {"PATH": str(self.bin)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def install_fake_ruff(self):
        """Put a ruff on PATH that logs its arguments to the returned file."""
        calls = self.bin.parent / "ruff-calls.txt"
        ruff = self.bin / "ruff"
        ruff.write_text(FAKE_RUFF.format(calls=calls))
        ruff.chmod(0o755)
        return calls

    def test_the_repos_local_oxfmt_runs_in_the_repo_whatever_the_callers_working_directory(self):
        local_bin = self.repo / "node_modules" / ".bin"
        local_bin.mkdir(parents=True)
        oxfmt = local_bin / "oxfmt"
        oxfmt.write_text("#!/bin/sh\nfor f in \"$@\"; do echo '// formatted' >> \"$f\"; done\n")
        oxfmt.chmod(0o755)
        # Like npx, the stand-in finds the tool relative to its own working directory, which must be the repo.
        npx = self.bin / "npx"
        npx.write_text("#!/bin/sh\ntool=\"$1\"\nshift\nexec ./node_modules/.bin/\"$tool\" \"$@\"\n")
        npx.chmod(0o755)
        (self.repo / "src").mkdir()
        (self.repo / "src" / "a.ts").write_text("const a = 1\n")
        elsewhere = pathlib.Path(self.bin).parent
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(elsewhere)

        changed = format_files.run_formatters(str(self.repo), ["src/a.ts"])

        self.assertEqual(changed, ["src/a.ts"])
        self.assertEqual((self.repo / "src" / "a.ts").read_text(), "const a = 1\n// formatted\n")

    def install_recording_web_formatters(self, linters=()):
        """Put a recording npx (the formatters' launcher) and the named linters on PATH. Each logs its arguments to
        the returned file; a linter's line starts with its name."""
        calls = self.bin.parent / "formatter-calls.txt"
        npx = self.bin / "npx"
        npx.write_text(f"#!/bin/sh\necho \"$@\" >> {calls}\n")
        npx.chmod(0o755)
        for name in linters:
            linter = self.bin / name
            linter.write_text(f"#!/bin/sh\necho \"{name} $@\" >> {calls}\n")
            linter.chmod(0o755)
        return calls

    def test_the_loop_path_runs_no_web_formatter_in_a_repo_that_configures_none_and_holds_none(self):
        calls = self.install_recording_web_formatters()
        (self.repo / "a.ts").write_text("const a = 1\n")
        (self.repo / "package.json").write_text('{"name": "shop"}\n')

        format_files.run_formatters(str(self.repo), ["a.ts"], configured_only=True)
        self.assertFalse(calls.exists())

        format_files.run_formatters(str(self.repo), ["a.ts"])
        self.assertIn("prettier --write a.ts", calls.read_text())

    def test_the_loop_path_runs_a_web_formatter_the_repo_configures(self):
        configured = {"prettier key in package.json": ("package.json", '{"prettier": {}}', "prettier --write a.ts"),
                      "eslintConfig key in package.json": ("package.json", '{"eslintConfig": {}}', "eslint --fix"),
                      ".prettierrc": (".prettierrc", "{}", "prettier --write a.ts"),
                      ".oxfmtrc.json": (".oxfmtrc.json", "{}", "oxfmt a.ts")}
        (self.repo / "a.ts").write_text("const a = 1\n")
        for name, (file_name, text, expected) in configured.items():
            with self.subTest(name):
                # A configured web linter runs only when it can run.
                calls = self.install_recording_web_formatters(("eslint",))
                calls.unlink(missing_ok=True)
                for stale in ("package.json", ".prettierrc", ".oxfmtrc.json"):
                    (self.repo / stale).unlink(missing_ok=True)
                (self.repo / file_name).write_text(text)

                format_files.run_formatters(str(self.repo), ["a.ts"], configured_only=True)

                self.assertIn(expected, calls.read_text())

    def test_a_configured_but_missing_oxlint_does_not_displace_a_configured_eslint(self):
        calls = self.install_recording_web_formatters(("eslint",))
        calls.unlink(missing_ok=True)
        (self.repo / "a.ts").write_text("const a = 1\n")
        (self.repo / ".oxlintrc.json").write_text("{}")
        (self.repo / "eslint.config.js").write_text("export default []\n")

        format_files.run_formatters(str(self.repo), ["a.ts"], configured_only=True)

        recorded = calls.read_text()
        self.assertIn("eslint --fix", recorded)
        self.assertNotIn("oxlint", recorded)

    def test_ruff_runs_only_in_a_repo_that_configures_it(self):
        self.install_fake_ruff()
        (self.repo / "app.py").write_text("x = 1\n")
        unconfigured = {"none": None, "pyproject without a ruff table": ("pyproject.toml", "[tool.black]\n"),
                        "broken pyproject": ("pyproject.toml", "[tool.ruff\n")}
        configured = {"pyproject": ("pyproject.toml", "[tool.ruff]\nline-length = 100\n"),
                      "ruff.toml": ("ruff.toml", ""), ".ruff.toml": (".ruff.toml", "")}
        for name, config in unconfigured.items():
            with self.subTest(name):
                if config:
                    (self.repo / config[0]).write_text(config[1])

                self.assertEqual(format_files.run_formatters(str(self.repo), ["app.py"], include_python=True), [])
        for name, (file_name, text) in configured.items():
            with self.subTest(name):
                for stale in ("pyproject.toml", "ruff.toml", ".ruff.toml"):
                    (self.repo / stale).unlink(missing_ok=True)
                (self.repo / file_name).write_text(text)
                (self.repo / "app.py").write_text("x = 1\n")

                self.assertEqual(format_files.run_formatters(str(self.repo), ["app.py"], include_python=True),
                                 ["app.py"])

    def test_ruff_runs_in_a_repo_whose_only_ruff_setup_is_pre_commit_hooks(self):
        calls = self.install_fake_ruff()
        both_hooks = TLDR_PRE_COMMIT_CONFIG
        check_only = TLDR_PRE_COMMIT_CONFIG.replace("      - id: ruff-format\n        files: ^backend/\n", "")
        other_hooks_only = "repos:\n  - repo: local\n    hooks:\n      - id: mypy\n      - id: ruff-like\n"
        quoted_format_id = "repos:\n  - repo: r\n    hooks:\n      - id: \"ruff-format\"\n"
        ruff_check_only = "repos:\n  - repo: r\n    hooks:\n      - id: ruff-check\n"
        # A trailing comment after the id still names the hook.
        commented_id = "repos:\n  - repo: r\n    hooks:\n      - id: ruff # lint\n"
        # YAML starts a comment only after whitespace, so this id is a different hook.
        hash_without_space = "repos:\n  - repo: r\n    hooks:\n      - id: ruff#x\n"
        cases = {"ruff and ruff-format hooks": (both_hooks, True, True),
                 "hash with no space before it": (hash_without_space, False, False),
                 "ruff hook only": (check_only, True, False),
                 "ruff-check hook only": (ruff_check_only, True, False),
                 "quoted ruff-format id": (quoted_format_id, True, True),
                 "ruff id with a trailing comment": (commented_id, True, False),
                 "no ruff hook": (other_hooks_only, False, False)}
        for name, (config, checks, formats) in cases.items():
            with self.subTest(name):
                calls.unlink(missing_ok=True)
                (self.repo / ".pre-commit-config.yaml").write_text(config)
                (self.repo / "app.py").write_text("x = 1\n")

                format_files.run_formatters(str(self.repo), ["app.py"], include_python=True, configured_only=True)

                recorded = calls.read_text() if calls.exists() else ""
                self.assertEqual("check --fix" in recorded, checks, recorded)
                self.assertEqual("format " in recorded, formats, recorded)

    def test_python_files_are_formatted_only_when_asked_and_the_changed_ones_are_returned(self):
        (self.repo / "ruff.toml").write_text("")
        self.install_fake_ruff()
        (self.repo / "app.py").write_text("x = 1\n")

        without = format_files.run_formatters(str(self.repo), ["app.py"])
        with_python = format_files.run_formatters(str(self.repo), ["app.py"], include_python=True)

        self.assertEqual((without, with_python), ([], ["app.py"]))
        self.assertEqual((self.repo / "app.py").read_text(), "x = 1\n# formatted\n")

    def test_the_loop_path_runs_ruff_format_only_in_a_repo_that_shows_it_formats_with_ruff(self):
        self.install_fake_ruff()
        cases = {"lint-only [tool.ruff]": ("pyproject.toml", "[tool.ruff]\nline-length = 100\n", "", False),
                 "ruff.toml without a format table": ("ruff.toml", "line-length = 100\n", "", False),
                 "[tool.ruff.format]": ("pyproject.toml", "[tool.ruff.format]\nquote-style = 'single'\n", "", True),
                 "[format] in ruff.toml": ("ruff.toml", "[format]\nindent-style = 'tab'\n", "", True),
                 "[format] in .ruff.toml": (".ruff.toml", "[format]\nindent-style = 'tab'\n", "", True),
                 "ruff format in the pre-commit config": (".pre-commit-config.yaml", "entry: ruff format\n", "", True),
                 "ruff format in the check command": ("ruff.toml", "", "ruff format --check . && pytest", True)}
        for name, (file_name, text, check_command, formats) in cases.items():
            with self.subTest(name):
                for stale in ("pyproject.toml", "ruff.toml", ".ruff.toml", ".pre-commit-config.yaml"):
                    (self.repo / stale).unlink(missing_ok=True)
                (self.repo / file_name).write_text(text)
                if file_name == ".pre-commit-config.yaml":
                    (self.repo / "ruff.toml").write_text("")
                (self.repo / "app.py").write_text("x = 1\n")

                changed = format_files.run_formatters(str(self.repo), ["app.py"], include_python=True,
                                                      configured_only=True, check_command=check_command)

                self.assertEqual(changed, ["app.py"] if formats else [])

    def install_fake_rustfmt(self):
        """A rustfmt that logs its arguments and appends a line to each .rs file it is given."""
        calls = self.bin.parent / "rustfmt-calls"
        rustfmt = self.bin / "rustfmt"
        rustfmt.write_text(f"""#!/bin/sh
echo "$@" >> {calls}
for f in "$@"; do case "$f" in *.rs) echo '// formatted' >> "$f";; esac; done
""")
        rustfmt.chmod(0o755)
        return calls

    def test_the_loop_path_formats_rust_files_in_a_repo_whose_check_runs_cargo_fmt(self):
        calls = self.install_fake_rustfmt()
        (self.repo / "Cargo.toml").write_text('[package]\nname = "app"\nedition = "2024"\n')
        (self.repo / "src").mkdir()
        (self.repo / "src" / "main.rs").write_text("fn main() {}\n")

        changed = format_files.run_formatters(str(self.repo), ["src/main.rs"], include_python=True,
                                              configured_only=True, check_command="cargo fmt --check && cargo test")

        self.assertEqual(changed, ["src/main.rs"])
        self.assertEqual(calls.read_text(), "--edition 2024 src/main.rs\n")

    def test_rust_files_take_the_edition_their_crate_inherits_from_the_workspace(self):
        calls = self.install_fake_rustfmt()
        (self.repo / "rustfmt.toml").write_text("")
        (self.repo / "Cargo.toml").write_text('[workspace]\nmembers = ["app"]\n[workspace.package]\nedition = "2018"\n')
        (self.repo / "app" / "src").mkdir(parents=True)
        (self.repo / "app" / "Cargo.toml").write_text('[package]\nname = "app"\nedition.workspace = true\n')
        (self.repo / "app" / "src" / "lib.rs").write_text("pub fn f() {}\n")
        (self.repo / "loose.rs").write_text("fn g() {}\n")

        changed = format_files.run_formatters(str(self.repo), ["app/src/lib.rs", "loose.rs"])

        self.assertEqual(sorted(changed), ["app/src/lib.rs", "loose.rs"])
        self.assertEqual(calls.read_text(), "--edition 2018 app/src/lib.rs loose.rs\n")

    def test_rust_files_are_left_alone_in_a_repo_that_shows_no_rustfmt_use(self):
        calls = self.install_fake_rustfmt()
        (self.repo / "Cargo.toml").write_text('[package]\nname = "app"\nedition = "2021"\n')
        (self.repo / "main.rs").write_text("fn main() {}\n")

        changed = format_files.run_formatters(str(self.repo), ["main.rs"], include_python=True, configured_only=True,
                                              check_command="cargo test")

        self.assertEqual(changed, [])
        self.assertFalse(calls.exists())

    def test_a_missing_ruff_a_missing_file_and_a_plan_file_are_skipped_silently(self):
        (self.repo / "ruff.toml").write_text("")
        (self.repo / "docs" / "plans").mkdir(parents=True)
        (self.repo / "docs" / "plans" / "plan.py").write_text("x = 1\n")
        (self.repo / "app.py").write_text("x = 1\n")
        self.install_fake_ruff()

        changed = format_files.run_formatters(str(self.repo), ["gone.py", "docs/plans/plan.py"], include_python=True)
        (self.bin / "ruff").unlink()
        no_ruff = format_files.run_formatters(str(self.repo), ["app.py"], include_python=True)

        self.assertEqual((changed, no_ruff), ([], []))
        self.assertEqual((self.repo / "app.py").read_text(), "x = 1\n")

    def test_prompt_markdown_is_never_formatted_but_other_files_beside_it_are(self):
        calls = self.install_recording_web_formatters()
        prompt_files = ["claude/.claude/agents/x.md", "opencode/.config/opencode/agents/x.md", "sub/CLAUDE.md",
                        "AGENTS.md", "sub/CLAUDE.local.md"]
        for name in [*prompt_files, "claude/.claude/settings.json", "docs/readme.md"]:
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / name).write_text("> quote\nplain line\n")

        format_files.run_formatters(str(self.repo), prompt_files)
        self.assertFalse(calls.exists())

        format_files.run_formatters(str(self.repo), [*prompt_files, "claude/.claude/settings.json", "docs/readme.md"])
        self.assertIn("prettier --write claude/.claude/settings.json docs/readme.md\n", calls.read_text())


@unittest.skipUnless(shutil.which("ruff"), "ruff is not on PATH")
class LintProblemsTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.repo = pathlib.Path(scratch.name)
        (self.repo / "tests").mkdir()

    def write_test_file(self, text):
        (self.repo / "tests" / "test_x.py").write_text(text)

    def configure_ruff(self):
        (self.repo / "ruff.toml").write_text('[lint]\nselect = ["N802"]\n')

    def test_an_unfixable_violation_in_a_test_file_comes_back_with_the_linter_output(self):
        self.configure_ruff()
        self.write_test_file("def testCamel():\n    pass\n")

        problems = format_files.lint_problems(str(self.repo), ["tests/test_x.py"])

        self.assertEqual(len(problems), 1, problems)
        command, output = problems[0]
        self.assertTrue(command.startswith("ruff check"), command)
        self.assertIn("tests/test_x.py", output)

    def test_a_repo_with_no_ruff_config_has_no_problems(self):
        self.write_test_file("def testCamel():\n    pass\n")

        problems = format_files.lint_problems(str(self.repo), ["tests/test_x.py"])

        self.assertEqual(problems, [])

    def test_a_clean_file_has_no_problems(self):
        self.configure_ruff()
        self.write_test_file("def test_snake():\n    pass\n")

        problems = format_files.lint_problems(str(self.repo), ["tests/test_x.py"])

        self.assertEqual(problems, [])

    def test_a_file_the_ruff_config_excludes_is_not_linted_when_named(self):
        (self.repo / "ruff.toml").write_text('extend-exclude = ["gen"]\n[lint]\nselect = ["N802"]\n')
        (self.repo / "gen").mkdir()
        (self.repo / "gen" / "x.py").write_text("def testCamel():\n    pass\n")

        problems = format_files.lint_problems(str(self.repo), ["gen/x.py"])

        self.assertEqual(problems, [])


class PreCommitOnlyLintProblemsTest(unittest.TestCase):
    def test_a_failing_ruff_check_is_reported_in_a_repo_whose_only_ruff_setup_is_pre_commit_hooks(self):
        with tempfile.TemporaryDirectory() as scratch:
            repo = pathlib.Path(scratch) / "repo"
            fake_bin = pathlib.Path(scratch) / "bin"
            repo.mkdir()
            fake_bin.mkdir()
            ruff = fake_bin / "ruff"
            ruff.write_text("#!/bin/sh\necho 'app.py:1:1: N802 bad name'\nexit 1\n")
            ruff.chmod(0o755)
            (repo / ".pre-commit-config.yaml").write_text(TLDR_PRE_COMMIT_CONFIG)
            (repo / "app.py").write_text("x = 1\n")

            with mock.patch.dict(os.environ, {"PATH": str(fake_bin)}):
                problems = format_files.lint_problems(str(repo), ["app.py"])

        self.assertEqual(len(problems), 1, problems)
        command, output = problems[0]
        self.assertTrue(command.startswith("ruff check"), command)
        self.assertIn("N802", output)


class RuffMissingFromPathTest(unittest.TestCase):
    def test_a_configured_ruff_that_is_not_on_path_is_never_run(self):
        with tempfile.TemporaryDirectory() as scratch:
            repo = pathlib.Path(scratch) / "repo"
            empty_bin = pathlib.Path(scratch) / "bin"
            repo.mkdir()
            empty_bin.mkdir()
            (repo / "ruff.toml").write_text('[lint]\nselect = ["N802"]\n')
            (repo / "x.py").write_text("def testCamel():\n    pass\n")

            with mock.patch.dict(os.environ, {"PATH": str(empty_bin)}), \
                    mock.patch.object(script_utils, "run_command") as run_command:
                problems = format_files.lint_problems(str(repo), ["x.py"])

        self.assertEqual(problems, [])
        run_command.assert_not_called()


class WebLintProblemsTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.repo = pathlib.Path(scratch.name) / "repo"
        self.repo.mkdir()
        self.bin = pathlib.Path(scratch.name) / "bin"
        self.bin.mkdir()
        # Only the fake bin: a real oxlint or eslint on the machine's PATH would change the outcome.
        patcher = mock.patch.dict(os.environ, {"PATH": str(self.bin)})
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.repo / "a.ts").write_text("const a = 1\n")

    def install_fake_npx(self, exit_code):
        npx = self.bin / "npx"
        npx.write_text(f"#!/bin/sh\necho \"npx $*\"\nexit {exit_code}\n")
        npx.chmod(0o755)

    def install_linter(self, directory, name, exit_code):
        directory.mkdir(parents=True, exist_ok=True)
        linter = directory / name
        linter.write_text(f"#!/bin/sh\necho \"{name} from {directory.name} $*\"\nexit {exit_code}\n")
        linter.chmod(0o755)

    def install_local_linter(self, name, exit_code):
        self.install_linter(self.repo / "node_modules" / ".bin", name, exit_code)

    def test_a_failing_installed_oxlint_comes_back_as_a_problem_without_fix(self):
        (self.repo / ".oxlintrc.json").write_text("{}")
        self.install_local_linter("oxlint", 1)

        problems = format_files.lint_problems(str(self.repo), ["a.ts"])

        self.assertEqual(len(problems), 1, problems)
        command, output = problems[0]
        self.assertIn("oxlint", command)
        self.assertNotIn("--fix", command)
        self.assertIn("oxlint from .bin", output)

    def test_a_failing_installed_eslint_comes_back_as_a_problem_with_the_check_flags(self):
        (self.repo / "eslint.config.js").write_text("export default []\n")
        self.install_local_linter("eslint", 1)

        problems = format_files.lint_problems(str(self.repo), ["a.ts"])

        self.assertEqual(len(problems), 1, problems)
        command, output = problems[0]
        self.assertNotIn("--fix", command)
        self.assertIn("--no-warn-ignored", output)
        self.assertNotIn("--max-warnings", output)

    def test_a_legacy_eslintrc_repo_gets_no_flat_config_only_flag(self):
        (self.repo / ".eslintrc.json").write_text("{}\n")
        self.install_local_linter("eslint", 1)

        problems = format_files.lint_problems(str(self.repo), ["a.ts"])

        self.assertEqual(len(problems), 1, problems)
        command, output = problems[0]
        self.assertNotIn("--fix", command)
        self.assertEqual(output.strip(), "eslint from .bin a.ts")

    def test_a_passing_oxlint_has_no_problems(self):
        (self.repo / ".oxlintrc.json").write_text("{}")
        self.install_local_linter("oxlint", 0)

        self.assertEqual(format_files.lint_problems(str(self.repo), ["a.ts"]), [])

    def test_the_fix_pass_runs_an_installed_oxlint_the_repo_does_not_configure_but_the_check_does_not(self):
        oxlint_calls = self.bin.parent / "oxlint-local-calls.txt"
        local_bin = self.repo / "node_modules" / ".bin"
        local_bin.mkdir(parents=True)
        oxlint = local_bin / "oxlint"
        oxlint.write_text(f"#!/bin/sh\necho \"$@\" >> {oxlint_calls}\nexit 1\n")
        oxlint.chmod(0o755)
        (self.repo / "a.ts").write_text("const a = 1\n")

        format_files.run_formatters(str(self.repo), ["a.ts"], configured_only=True)

        self.assertIn("--fix a.ts", oxlint_calls.read_text())
        oxlint_calls.unlink()
        self.assertEqual(format_files.lint_problems(str(self.repo), ["a.ts"]), [])
        self.assertFalse(oxlint_calls.exists())

    def test_a_linter_installed_but_not_configured_is_not_run(self):
        self.install_local_linter("oxlint", 1)
        self.install_local_linter("eslint", 2)

        self.assertEqual(format_files.lint_problems(str(self.repo), ["a.ts"]), [])

    def test_a_path_installed_oxlint_runs_from_path_not_through_npx(self):
        (self.repo / ".oxlintrc.json").write_text("{}")
        self.install_linter(self.bin, "oxlint", 1)
        self.install_fake_npx(1)

        problems = format_files.lint_problems(str(self.repo), ["a.ts"])

        self.assertEqual(len(problems), 1, problems)
        command, output = problems[0]
        self.assertNotIn("npx", command)
        self.assertIn("oxlint from bin", output)
        self.assertNotIn("npx", output)

    def test_a_path_installed_oxlint_is_fixed_from_path_without_npx(self):
        (self.repo / ".oxlintrc.json").write_text("{}")
        npx_calls = self.bin.parent / "npx-calls.txt"
        npx = self.bin / "npx"
        npx.write_text(f"#!/bin/sh\necho \"$@\" >> {npx_calls}\n")
        npx.chmod(0o755)
        oxlint_calls = self.bin.parent / "oxlint-calls.txt"
        oxlint = self.bin / "oxlint"
        oxlint.write_text(f"#!/bin/sh\necho \"$@\" >> {oxlint_calls}\n")
        oxlint.chmod(0o755)

        format_files.run_formatters(str(self.repo), ["a.ts"], configured_only=True)

        self.assertIn("--fix a.ts", oxlint_calls.read_text())
        self.assertFalse(npx_calls.exists())

    def test_an_installed_eslint_runs_when_oxlint_is_configured_but_missing(self):
        (self.repo / ".oxlintrc.json").write_text("{}")
        (self.repo / "eslint.config.js").write_text("export default []\n")
        self.install_local_linter("eslint", 1)

        problems = format_files.lint_problems(str(self.repo), ["a.ts"])

        self.assertEqual(len(problems), 1, problems)
        self.assertIn("eslint", problems[0][0])

    def test_a_configured_but_not_installed_oxlint_is_not_run(self):
        (self.repo / ".oxlintrc.json").write_text("{}")
        self.install_fake_npx(1)

        self.assertEqual(format_files.lint_problems(str(self.repo), ["a.ts"]), [])

    def test_a_missing_or_plan_file_is_never_linted(self):
        (self.repo / ".oxlintrc.json").write_text("{}")
        self.install_local_linter("oxlint", 1)
        (self.repo / "docs" / "plans").mkdir(parents=True)
        (self.repo / "docs" / "plans" / "p.ts").write_text("const p = 1\n")

        problems = format_files.lint_problems(str(self.repo), ["gone.ts", "docs/plans/p.ts"])

        self.assertEqual(problems, [])

    def test_a_missing_program_is_no_lint_problem(self):
        self.assertEqual(format_files.lint_command_problem(["no-such-binary"], str(self.repo)), [])

    def test_a_timed_out_linter_is_a_lint_problem(self):
        timed_out = (script_utils.TIMEOUT_EXIT_CODE, "x")
        with mock.patch.object(script_utils, "run_command", return_value=timed_out) as run_command:
            self.assertEqual(format_files.lint_command_problem(["ruff", "check"], str(self.repo)),
                             [("ruff check", "x")])
        run_command.assert_called_once_with(["ruff", "check"], str(self.repo),
                                            timeout=format_files.LINT_TIMEOUT_SECONDS)


if __name__ == "__main__":
    unittest.main()
