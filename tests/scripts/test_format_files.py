"""Checks for format_files.py, the shared autofix formatter runner of the format hook and the review loop.

Formatters are fake executables on PATH; the hook's own tests cover the web tool choice."""
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import format_files

FAKE_RUFF = """#!/bin/sh
[ "$1" = format ] || exit 0
shift
for f in "$@"; do echo '# formatted' >> "$f"; done
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
        ruff = self.bin / "ruff"
        ruff.write_text(FAKE_RUFF)
        ruff.chmod(0o755)

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

    def install_recording_npx(self):
        calls = self.bin.parent / "npx-calls.txt"
        npx = self.bin / "npx"
        npx.write_text(f"#!/bin/sh\necho \"$@\" >> {calls}\n")
        npx.chmod(0o755)
        return calls

    def test_the_loop_path_runs_no_web_formatter_in_a_repo_that_configures_none_and_holds_none(self):
        calls = self.install_recording_npx()
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
                calls = self.install_recording_npx()
                calls.unlink(missing_ok=True)
                for stale in ("package.json", ".prettierrc", ".oxfmtrc.json"):
                    (self.repo / stale).unlink(missing_ok=True)
                (self.repo / file_name).write_text(text)

                format_files.run_formatters(str(self.repo), ["a.ts"], configured_only=True)

                self.assertIn(expected, calls.read_text())

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


if __name__ == "__main__":
    unittest.main()
