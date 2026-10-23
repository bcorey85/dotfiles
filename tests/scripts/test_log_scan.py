"""Checks for log-scan: it writes one scan_run row through `ledger write`.

A stand-in `ledger` (fake_ledger) records what the script sends. Every case runs with HOME set to a temp dir,
so nothing reaches a real log.

Script location: LOG_SCAN_SCRIPT, defaulting to ~/.claude/scripts/log-scan.
"""
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import fake_ledger

SCRIPT = pathlib.Path(os.environ.get("LOG_SCAN_SCRIPT") or pathlib.Path.home() / ".claude" / "scripts" / "log-scan")

RAN_ARGS = ["scan=prohibition", "stage=manual", "exit=0", "candidates=2", "confirmed=1"]


class LogScanTest(unittest.TestCase):
    def setUp(self):
        tempDir = tempfile.TemporaryDirectory()
        self.addCleanup(tempDir.cleanup)
        self.tempRoot = pathlib.Path(tempDir.name).resolve()
        self.home = self.tempRoot / "home"
        (self.home / ".claude").mkdir(parents=True)
        self.ledgerEnv = fake_ledger.install(self.tempRoot)

    def environment(self, **extra):
        callerEnv = {key: value for key, value in os.environ.items()
                     if key not in ("CLAUDE_TOOLKIT_TELEMETRY", "CLAUDE_CODE_SESSION_ID")}
        return {**callerEnv, **self.ledgerEnv, "HOME": str(self.home), "CLAUDE_TOOLKIT_TELEMETRY": "1", **extra}

    def run_scan(self, *args, env=None):
        return subprocess.run(["bash", str(SCRIPT), *args], cwd=self.tempRoot, env=env or self.environment(),
                              capture_output=True, text=True)

    def scanRows(self):
        return fake_ledger.recorded_rows(self.ledgerEnv, "scan_run")

    def test_writes_scan_run(self):
        done = self.run_scan(*RAN_ARGS, "fixed=1", "fp=1")
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))
        rows = self.scanRows()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["scan"], rows[0]["stage"], rows[0]["exit"]), ("prohibition", "manual", "0"))
        self.assertEqual((rows[0]["candidates"], rows[0]["confirmed"], rows[0]["fixed"]), ("2", "1", "1"))
        for field in ("date", "schema_version", "repo", "session"):
            self.assertNotIn(field, rows[0])

    def test_drops_note(self):
        done = self.run_scan(*RAN_ARGS, "note=planted note, with spaces")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("note", self.scanRows()[0])

    def test_renames_branch_to_branch_key(self):
        done = self.run_scan(*RAN_ARGS, "branch=planted-branch-zq")
        self.assertEqual(done.returncode, 0, done.stderr)
        row = self.scanRows()[0]
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
        self.assertEqual(len(self.scanRows()), 1)

    def test_exit_1_needs_zero_candidates(self):
        done = self.run_scan("scan=prohibition", "stage=manual", "exit=1", "candidates=3", "confirmed=0")
        self.assertEqual(done.returncode, 1)
        self.assertIn("exit=1 means the scan ran and printed nothing", done.stderr)
        self.assertEqual(self.scanRows(), [])
        done = self.run_scan("scan=prohibition", "stage=manual", "exit=1", "candidates=0", "confirmed=0")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(self.scanRows()), 1)

    def test_confirmed_over_candidates_is_refused(self):
        done = self.run_scan("scan=prohibition", "stage=manual", "exit=0", "candidates=1", "confirmed=2")
        self.assertEqual(done.returncode, 1)
        self.assertIn("refusing to log: confirmed (2) exceeds candidates (1).", done.stderr)
        self.assertEqual(self.scanRows(), [])

    def test_unknown_scan_reaches_the_ledger(self):
        done = self.run_scan("scan=nonsense", "stage=manual", "exit=2")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.scanRows()[0]["scan"], "nonsense")

    def test_repo_is_not_required(self):
        done = self.run_scan(*RAN_ARGS)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("repo", self.scanRows()[0])

    def test_telemetry_off_is_silent(self):
        done = self.run_scan(*RAN_ARGS, env=self.environment(CLAUDE_TOOLKIT_TELEMETRY="0"))
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))
        self.assertEqual(self.scanRows(), [])

    def test_no_ledger_on_path_exits_0_silently(self):
        noLedger = fake_ledger.no_ledger_env(self.tempRoot)
        self.assertIsNone(shutil.which("ledger", path=noLedger["PATH"]))
        done = self.run_scan(*RAN_ARGS, env=self.environment(**noLedger))
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))
        self.assertEqual(list(pathlib.Path(noLedger["AGENT_LEDGER_ROOT"]).iterdir()), [])
        self.assertEqual(self.scanRows(), [])

    def test_retired_scan_runs_file_var_writes_no_file(self):
        retired = self.tempRoot / "retired-scan-runs.jsonl"
        done = self.run_scan(*RAN_ARGS, env=self.environment(SCAN_RUNS_FILE=str(retired)))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse(retired.exists())
        self.assertFalse((self.home / ".claude" / "scan-runs.jsonl").exists())
        self.assertEqual(len(self.scanRows()), 1)


if __name__ == "__main__":
    unittest.main()
