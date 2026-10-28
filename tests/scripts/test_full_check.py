"""Checks for full_check.py, the review loop's full check under a time limit.

Set FULL_CHECK_SCRIPT to run against another copy, such as a staged one."""
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("FULL_CHECK_SCRIPT") or toolkit_paths.REVIEW_DIR / "full_check.py")


class FullCheckTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.repo = pathlib.Path(scratch.name)
        self.log = self.repo / "review-gate.log"

    def check(self, command, claude_md=None, timeout=None, env=None):
        if claude_md is not None:
            (self.repo / "CLAUDE.md").write_text(claude_md)
        argv = [sys.executable, "-B", str(SCRIPT), str(self.repo), "--log", str(self.log)]
        if timeout is not None:
            argv += ["--timeout", str(timeout)]
        return subprocess.run([*argv, "--", command], capture_output=True, text=True, timeout=60, env=env)

    def pyenv_root_with_a_python3_shim(self):
        pyenv_root = self.repo / "pyenv-root"
        shim = pyenv_root / "shims" / "python3"
        shim.parent.mkdir(parents=True)
        shim.write_text("#!/bin/sh\necho pinned python3\n")
        shim.chmod(0o755)
        return pyenv_root

    def test_a_repo_with_a_python_version_file_runs_python3_through_the_pyenv_shims(self):
        (self.repo / ".python-version").write_text("3.12.4\n")
        pyenv_root = self.pyenv_root_with_a_python3_shim()

        completed = self.check("python3", env={**os.environ, "PYENV_ROOT": str(pyenv_root)})

        self.assertEqual(completed.stdout.splitlines()[0], "full check: passed", completed.stdout)
        self.assertEqual(self.log.read_text(), "pinned python3\n")

    def test_a_repo_with_no_python_version_file_keeps_the_path_as_it_is(self):
        pyenv_root = self.pyenv_root_with_a_python3_shim()

        self.check("command -v python3", env={**os.environ, "PYENV_ROOT": str(pyenv_root)})

        self.assertNotIn(str(pyenv_root), self.log.read_text())

    def missing_module_check(self, module):
        return self.check(f"echo \"ModuleNotFoundError: No module named '{module}'\"; exit 1")

    def test_a_missing_declared_module_is_an_environment_gap_not_a_failure(self):
        (self.repo / "requirements-dev.txt").write_text("# dev tools\n-r requirements.txt\nruff==0.6.9\n")

        completed = self.missing_module_check("ruff")

        self.assertEqual(completed.returncode, 0, completed.stdout)
        self.assertEqual(completed.stdout.splitlines()[0],
                         "full check: not run (environment gap: No module named 'ruff')")

    def test_a_missing_undeclared_module_is_a_failure(self):
        (self.repo / "requirements.txt").write_text("flask>=3\n")

        completed = self.missing_module_check("requests")

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.splitlines()[0], "full check: failed (exit 1)")

    def test_each_dependency_file_shape_declares_its_modules_by_normalized_name(self):
        dependency_files = {
            "pyproject.toml": ('[project]\ndependencies = ["Typing_Extensions>=4"]\n'
                               '[project.optional-dependencies]\ndev = ["pytest-cov"]\n'
                               '[dependency-groups]\nlint = ["mypy", {include-group = "test"}]\n'
                               '[tool.poetry.group.docs.dependencies]\nsphinx = "^7"\n'),
            "setup.cfg": "[options]\ninstall_requires =\n    attrs>=23\n[options.extras_require]\nyaml = PyYAML\n",
            "Pipfile": '[packages]\nrich = "*"\n[dev-packages]\nblack = "*"\n',
        }
        for name, text in dependency_files.items():
            (self.repo / name).write_text(text)

        for module in ("typing_extensions", "pytest_cov", "mypy", "sphinx.ext", "attrs", "yaml", "rich", "black"):
            with self.subTest(module=module):
                completed = self.missing_module_check(module)

                expected = "full check: not run" if module != "yaml" else "full check: failed"
                self.assertTrue(completed.stdout.startswith(expected), completed.stdout)

    def test_a_missing_module_of_the_repo_itself_is_a_failure(self):
        (self.repo / "orders").mkdir()

        completed = self.missing_module_check("orders.totals")

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.splitlines()[0], "full check: failed (exit 1)")

    def test_a_passing_check_prints_passed(self):
        completed = self.check("echo ok")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.splitlines()[0], "full check: passed")
        self.assertEqual(self.log.read_text(), "ok\n")

    def test_a_failing_check_prints_its_exit_code_and_the_log_tail(self):
        completed = self.check("echo the rounding test failed; exit 3")

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.splitlines(), ["full check: failed (exit 3)", "the rounding test failed"])

    def test_a_failing_lint_step_shows_its_error_lines_not_the_passing_test_tail(self):
        stand_in = ("printf 'C901 `command_asks_done` is too complex (12 > 10)\\n  --> app.py:12:5\\n'; "
                    "for n in $(seq 1 60); do echo \"test_$n OK\"; done; echo '60 tests, 0 failed'; "
                    "echo 'FAILED: lint'; exit 1")

        completed = self.check(stand_in)

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.splitlines(), ["full check: failed (exit 1)",
                                                         "C901 `command_asks_done` is too complex (12 > 10)",
                                                         "  --> app.py:12:5", "FAILED: lint"])

    def test_a_failing_test_step_shows_its_fail_lines(self):
        completed = self.check("echo 'FAIL: test_rounding (test_money.MoneyTest)'; echo 'Ran 9 tests'; exit 1")

        self.assertIn("FAIL: test_rounding (test_money.MoneyTest)", completed.stdout.splitlines())

    def test_a_step_on_a_missing_path_is_a_check_command_error_not_a_failure(self):
        for command in ("git init -q && git diff --exit-code missing/schema.json", "cd missing-dir && true"):
            with self.subTest(command=command):
                completed = self.check(command)

                self.assertEqual(completed.returncode, 0, completed.stdout)
                first_line = completed.stdout.splitlines()[0]
                self.assertTrue(first_line.startswith("full check: not run (check-command error: "), first_line)
                self.assertIn("missing", first_line)

    def test_a_step_on_a_path_the_diff_removed_is_a_failure(self):
        (self.repo / "pkg").mkdir()
        (self.repo / "pkg" / "schema.json").write_text("{}\n")
        for argv in (["init", "-q"], ["add", "pkg"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                                                      "-m", "base"], ["rm", "-q", "-r", "pkg"]):
            subprocess.run(["git", *argv], cwd=self.repo, check=True)

        for command in ("git diff --exit-code pkg/schema.json", "cd pkg && true"):
            with self.subTest(command=command):
                completed = self.check(command)

                self.assertEqual(completed.returncode, 1, completed.stdout)
                self.assertTrue(completed.stdout.startswith("full check: failed"), completed.stdout)

    def test_a_check_with_no_package_manifest_is_a_setup_fault(self):
        completed = self.check("echo ERR_PNPM_NO_IMPORTER_MANIFEST_FOUND; exit 1")

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.splitlines()[0], "full check: setup fault (exit 1)")

    def test_a_missing_module_from_outside_the_repo_is_a_failure_not_a_setup_fault(self):
        completed = self.check("echo \"ModuleNotFoundError: No module named 'requests'\"; exit 2")

        self.assertEqual(completed.stdout.splitlines()[0], "full check: failed (exit 2)")

    def test_a_failing_test_name_the_tail_cut_off_is_printed_above_the_tail(self):
        failing_test = "FAILED tests/test_totals.py::test_rounding"
        completed = self.check(f"echo '{failing_test}'; seq 1 100; exit 1")

        self.assertEqual(completed.stdout.splitlines()[:3],
                         ["full check: failed (exit 1)", "Failing tests:", failing_test])

    def test_a_check_past_its_limit_is_not_run_and_leaves_no_process_behind(self):
        pid_file = self.repo / "sleeper.pid"

        completed = self.check(f"sleep 30 & echo $! > {pid_file}; wait", timeout=1)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.splitlines()[0], "full check: not run (timeout)")
        sleeper = int(pid_file.read_text())
        time.sleep(0.2)
        with self.assertRaises(ProcessLookupError):
            os.kill(sleeper, 0)

    def test_the_full_suite_in_ci_line_skips_the_check(self):
        marker = self.repo / "ran"

        completed = self.check(f"touch {marker}", claude_md="# Repo\n\n- Full suite: CI\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.splitlines()[0], "full check: not run (CI)")
        self.assertFalse(marker.exists())

    def test_the_check_runs_when_claude_md_has_no_full_suite_line(self):
        completed = self.check("echo ok", claude_md="Quality check: `make test`\n")

        self.assertEqual(completed.stdout.splitlines()[0], "full check: passed")

    def test_a_misspelled_full_suite_line_still_runs_the_check(self):
        for line in ("Full suite: ci", "Full-suite: CI", "Full suite CI", "Full suite: CI runs it"):
            with self.subTest(line=line):
                completed = self.check("echo ok", claude_md=line + "\n")

                self.assertEqual(completed.stdout.splitlines()[0], "full check: passed")


if __name__ == "__main__":
    unittest.main()
