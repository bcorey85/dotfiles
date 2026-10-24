"""Checks for the metrics writers when no `ledger` is on PATH.

Each writer appends its row to the jsonl file its type used before the ledger, with date, schema_version,
repo and session added, and prints one stderr line. With the ledger present the row goes to the ledger
and no file is written. Every case runs in a temp git repo with HOME set to a temp dir.
"""

import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import fake_ledger
import toolkit_paths

REVIEW_SKILL_DIR = toolkit_paths.CLAUDE_DIR / "skills" / "review"
SESSION = "session-under-test"
REPO_NAME = "planted-repo"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}

# One case per row type: the writer, its arguments, the ledger type, the file and a field the row must hold.
CASES = {
    "review_finding": (
        REVIEW_SKILL_DIR / "log-review-finding",
        [
            "kind=finding",
            "gate=code-reviewer",
            "disposition=fix",
            "class=bug",
            "iter=1",
            "lane=none",
            "scope=phase",
            "actioned=fixed",
        ],
        "review-findings.jsonl",
        ("kind", "finding"),
    ),
    "review_run": (
        REVIEW_SKILL_DIR / "log-review-finding",
        ["kind=run", "gate=code-reviewer", "n_findings=2", "lane=none"],
        "review-findings.jsonl",
        ("kind", "run"),
    ),
    "review_metrics": (
        REVIEW_SKILL_DIR / "log-review-metrics",
        ["iter=2", "result=PASS"],
        "review-metrics.jsonl",
        ("iter", 2),
    ),
    "review_escape": (
        toolkit_paths.TELEMETRY_DIR / "log-escape",
        ["gate_missed=review", "stage_found=pr-human", "severity=high", "class=bug", "guard=none"],
        "review-escapes.jsonl",
        ("class", "bug"),
    ),
    "spec_run": (
        toolkit_paths.TELEMETRY_DIR / "log-spec-run",
        ["slug=my-plan", "verdict=finalized", "criteria=3"],
        "spec-runs.jsonl",
        ("criteria", 3),
    ),
    "scan_run": (
        toolkit_paths.TELEMETRY_DIR / "log-scan",
        ["scan=prohibition", "stage=manual", "exit=0", "candidates=2", "confirmed=1"],
        "scan-runs.jsonl",
        ("candidates", 2),
    ),
}


class LedgerWriteFallbackTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_root = pathlib.Path(temp_dir.name).resolve()
        self.home = self.temp_root / "home"
        self.home.mkdir()
        self.repo = self.temp_root / REPO_NAME
        self.repo.mkdir()
        self.git("init", "-q", "-b", "planted-branch")
        (self.repo / "kept.txt").write_text("one\n")
        self.git("add", "kept.txt")
        self.git("commit", "-q", "-m", "base")
        self.ledger_env = fake_ledger.install(self.temp_root)

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.repo, env={**os.environ, **GIT_ENV}, check=True, capture_output=True, text=True
        ).stdout.strip()

    def path_without_ledger(self):
        return os.pathsep.join(
            part for part in os.environ["PATH"].split(os.pathsep) if not os.path.exists(os.path.join(part, "ledger"))
        )

    def run_writer(self, script, args, with_ledger):
        caller_env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("CLAUDE_", "REVIEW_", "SPEC_RUNS", "SCAN_RUNS"))
        }
        env = {
            **caller_env,
            **GIT_ENV,
            "HOME": str(self.home),
            "CLAUDE_TOOLKIT_TELEMETRY": "1",
            "CLAUDE_CODE_SESSION_ID": SESSION,
        }
        env["PATH"] = self.ledger_env["PATH"] if with_ledger else self.path_without_ledger()
        if with_ledger:
            env["FAKE_LEDGER_ROWS"] = self.ledger_env["FAKE_LEDGER_ROWS"]
        else:
            self.assertIsNone(shutil.which("ledger", path=env["PATH"]))
        return subprocess.run(["bash", str(script), *args], cwd=self.repo, env=env, capture_output=True, text=True)

    def test_no_ledger_appends_the_completed_row_to_the_type_file_and_prints_one_stderr_line(self):
        for row_type, (script, args, file_name, (field, value)) in CASES.items():
            with self.subTest(row_type=row_type):
                done = self.run_writer(script, args, with_ledger=False)
                self.assertEqual(done.returncode, 0, done.stderr)
                log_path = self.home / ".claude" / file_name
                rows = [json.loads(line) for line in log_path.read_text().splitlines()]
                row = rows[-1]
                self.assertEqual(row[field], value)
                self.assertTrue(row["date"].endswith("Z"), row["date"])
                self.assertEqual((row["repo"], row["session"]), (REPO_NAME, SESSION))
                self.assertIsInstance(row["schema_version"], int)
                stderr_lines = done.stderr.strip().splitlines()
                self.assertEqual(len(stderr_lines), 1, done.stderr)
                self.assertIn(f"ledger not on PATH; row appended to {log_path}", stderr_lines[0])

    def test_with_the_ledger_the_row_goes_to_the_ledger_and_no_file_is_written(self):
        for row_type, (script, args, file_name, _expected) in CASES.items():
            with self.subTest(row_type=row_type):
                done = self.run_writer(script, args, with_ledger=True)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertNotIn("ledger not on PATH", done.stderr)
                self.assertEqual(len(fake_ledger.recorded_rows(self.ledger_env, row_type)), 1)
                self.assertFalse((self.home / ".claude" / file_name).exists())

    def test_a_failed_append_prints_one_stderr_line_and_exits_0(self):
        script, args, _file_name, _expected = CASES["review_escape"]
        blocker = self.home / ".claude"
        blocker.write_text("a file where the directory should be\n")
        done = self.run_writer(script, args, with_ledger=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(done.stderr.strip().splitlines()), 1, done.stderr)
        self.assertIn("could not append", done.stderr)


if __name__ == "__main__":
    unittest.main()
