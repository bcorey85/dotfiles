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

    def check(self, command, claude_md=None, timeout=None):
        if claude_md is not None:
            (self.repo / "CLAUDE.md").write_text(claude_md)
        argv = [sys.executable, "-B", str(SCRIPT), str(self.repo), "--log", str(self.log)]
        if timeout is not None:
            argv += ["--timeout", str(timeout)]
        return subprocess.run([*argv, "--", command], capture_output=True, text=True, timeout=60)

    def test_a_passing_check_prints_passed(self):
        completed = self.check("echo ok")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.splitlines()[0], "full check: passed")
        self.assertEqual(self.log.read_text(), "ok\n")

    def test_a_failing_check_prints_its_exit_code_and_the_log_tail(self):
        completed = self.check("echo the rounding test failed; exit 3")

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.splitlines(), ["full check: failed (exit 3)", "the rounding test failed"])

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
