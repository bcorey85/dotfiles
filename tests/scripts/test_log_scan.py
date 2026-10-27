"""Checks for log-scan: it writes one scan_run row through `ledger write`.

A stand-in `ledger` (fake_ledger) records what the script sends. Every case runs with HOME set to a temp dir,
so nothing reaches a real log.

Script location: LOG_SCAN_SCRIPT, defaulting to ~/.claude/scripts/telemetry/log-scan.
"""
import os
import pathlib
import subprocess
import tempfile
import unittest

import fake_ledger
import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("LOG_SCAN_SCRIPT") or toolkit_paths.TELEMETRY_DIR / "log-scan")

RAN_ARGS = ["scan=prohibition", "stage=manual", "exit=0", "candidates=2", "confirmed=1"]


class LogScanTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_root = pathlib.Path(temp_dir.name).resolve()
        self.home = self.temp_root / "home"
        (self.home / ".claude").mkdir(parents=True)
        self.ledger_env = fake_ledger.install(self.temp_root)

    def environment(self, **extra):
        caller_env = {key: value for key, value in os.environ.items()
                     if key not in ("CLAUDE_TOOLKIT_TELEMETRY", "CLAUDE_CODE_SESSION_ID")}
        return {**caller_env, **self.ledger_env, "HOME": str(self.home), "CLAUDE_TOOLKIT_TELEMETRY": "1", **extra}

    def run_scan(self, *args, env=None):
        return subprocess.run(["bash", str(SCRIPT), *args], cwd=self.temp_root, env=env or self.environment(),
                              capture_output=True, text=True)

    def scan_rows(self):
        return fake_ledger.recorded_rows(self.ledger_env, "scan_run")

    def test_writes_scan_run(self):
        done = self.run_scan(*RAN_ARGS, "fixed=1", "fp=1")
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))
        rows = self.scan_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["scan"], rows[0]["stage"], rows[0]["exit"]), ("prohibition", "manual", "0"))
        self.assertEqual((rows[0]["candidates"], rows[0]["confirmed"], rows[0]["fixed"]), ("2", "1", "1"))
        for field in ("date", "schema_version", "repo", "session"):
            self.assertNotIn(field, rows[0])

    def test_drops_note(self):
        done = self.run_scan(*RAN_ARGS, "note=planted note, with spaces")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("note", self.scan_rows()[0])

    def test_renames_branch_to_branch_key(self):
        done = self.run_scan(*RAN_ARGS, "branch=planted-branch-zq")
        self.assertEqual(done.returncode, 0, done.stderr)
        row = self.scan_rows()[0]
        self.assertEqual(row["branch_key"], "planted-branch-zq")
        self.assertNotIn("branch", row)

    def test_ran_scan_needs_counts(self):
        for code in ("0", "1"):
            with self.subTest(code=code):
                done = self.run_scan("scan=prohibition", "stage=manual", f"exit={code}")
                self.assertEqual(done.returncode, 1)
                self.assertIn("refusing to log: candidates= is required.", done.stderr)
        done = self.run_scan("scan=prohibition", "stage=manual", "exit=2")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(self.scan_rows()), 1)

    def test_exit_1_needs_zero_candidates(self):
        done = self.run_scan("scan=prohibition", "stage=manual", "exit=1", "candidates=3", "confirmed=0")
        self.assertEqual(done.returncode, 1)
        self.assertIn("exit=1 means the scan ran and printed nothing", done.stderr)
        self.assertEqual(self.scan_rows(), [])
        done = self.run_scan("scan=prohibition", "stage=manual", "exit=1", "candidates=0", "confirmed=0")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(self.scan_rows()), 1)

    def test_confirmed_over_candidates_is_refused(self):
        done = self.run_scan("scan=prohibition", "stage=manual", "exit=0", "candidates=1", "confirmed=2")
        self.assertEqual(done.returncode, 1)
        self.assertIn("refusing to log: confirmed (2) exceeds candidates (1).", done.stderr)
        self.assertEqual(self.scan_rows(), [])

    def test_unknown_scan_reaches_the_ledger(self):
        done = self.run_scan("scan=nonsense", "stage=manual", "exit=2")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.scan_rows()[0]["scan"], "nonsense")

    def test_repo_is_not_required(self):
        done = self.run_scan(*RAN_ARGS)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("repo", self.scan_rows()[0])

    def test_telemetry_off_is_silent(self):
        done = self.run_scan(*RAN_ARGS, env=self.environment(CLAUDE_TOOLKIT_TELEMETRY="0"))
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))
        self.assertEqual(self.scan_rows(), [])

    def test_retired_scan_runs_file_var_writes_no_file(self):
        retired = self.temp_root / "retired-scan-runs.jsonl"
        done = self.run_scan(*RAN_ARGS, env=self.environment(SCAN_RUNS_FILE=str(retired)))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse(retired.exists())
        self.assertFalse((self.home / ".claude" / toolkit_paths.local_stream_file("scan-runs")).exists())
        self.assertEqual(len(self.scan_rows()), 1)

    def test_help_prints_usage_and_writes_nothing(self):
        for flag in ("--help", "-h"):
            with self.subTest(flag=flag):
                done = self.run_scan(flag)
                self.assertEqual((done.returncode, done.stderr), (0, ""))
                self.assertIn("usage: log-scan key=value", done.stdout)
                self.assertEqual(fake_ledger.recorded_rows(self.ledger_env), [])


if __name__ == "__main__":
    unittest.main()
