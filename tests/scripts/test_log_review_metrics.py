import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import fake_ledger

os.environ.pop("CLAUDE_TOOLKIT_TELEMETRY", None)  # the switch file alone decides in these tests

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REAL_CLAUDE = REPO_ROOT / "claude" / ".claude"
SCRIPT = pathlib.Path(os.environ.get("LOG_REVIEW_METRICS_SCRIPT") or REAL_CLAUDE / "skills" / "review" / "log-review-metrics")
TELEMETRY_ENABLED_SCRIPT = pathlib.Path(os.environ.get("TELEMETRY_ENABLED_SCRIPT") or REAL_CLAUDE / "scripts" / "telemetry_enabled.sh")
KV_SCRIPT = REAL_CLAUDE / "scripts" / "_kv.sh"
LEDGER_WRITE_SCRIPT = REAL_CLAUDE / "scripts" / "ledger-write"

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}


class LogReviewMetricsRepoTest(unittest.TestCase):
    def setUp(self):
        tempDir = tempfile.TemporaryDirectory()
        self.addCleanup(tempDir.cleanup)
        self.root = pathlib.Path(tempDir.name)
        self.home = self.root / "home"
        (self.home / ".claude").mkdir(parents=True)
        (self.home / ".claude" / "toolkit-telemetry").touch()
        reviewDir = self.root / "claude" / "skills" / "review"
        self.scriptsDir = self.root / "claude" / "scripts"
        reviewDir.mkdir(parents=True)
        self.scriptsDir.mkdir()
        self.script = reviewDir / "log-review-metrics"
        shutil.copy2(SCRIPT, self.script)
        shutil.copy2(TELEMETRY_ENABLED_SCRIPT, self.scriptsDir / "telemetry_enabled.sh")
        shutil.copy2(KV_SCRIPT, self.scriptsDir / "_kv.sh")
        shutil.copy2(LEDGER_WRITE_SCRIPT, self.scriptsDir / "ledger-write")
        self.ledgerEnv = fake_ledger.install(self.root)

        self.mainRepo = self.root / "mainrepo"
        self.mainRepo.mkdir()
        self.git(self.mainRepo, "init", "-q")
        (self.mainRepo / "README.md").write_text("hello\n", encoding="utf-8")
        self.git(self.mainRepo, "add", "README.md")
        self.git(self.mainRepo, "commit", "-q", "-m", "init")
        self.worktree = self.root / "wt-some-branch"
        self.git(self.mainRepo, "worktree", "add", "-q", "-b", "some-branch", str(self.worktree))

    def git(self, cwd, *args):
        env = {**os.environ, **GIT_ENV}
        return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout

    def runMetrics(self, *args):
        env = {**os.environ, **GIT_ENV, "HOME": str(self.home), **self.ledgerEnv}
        return subprocess.run([str(self.script), *args], env=env, cwd=self.worktree, capture_output=True, text=True)

    def loggedMetricsRowAt(self, outValue, expectedLogPath, *args):
        metricsRun = self.runMetrics(f"out={outValue}", "iter=7", *args)
        self.assertEqual(metricsRun.returncode, 0, metricsRun.stderr)

        loggedLines = expectedLogPath.read_text().splitlines()
        self.assertEqual(len(loggedLines), 1)

        metricsRow = json.loads(loggedLines[0])
        self.assertEqual(metricsRow["iter"], "7")
        return metricsRow

    def ledgerRow(self, *args):
        metricsRun = self.runMetrics("iter=7", "result=PASS", *args)
        self.assertEqual(metricsRun.returncode, 0, metricsRun.stderr)
        rows = fake_ledger.recorded_rows(self.ledgerEnv, "review_metrics")
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_the_writer_runs_in_the_callers_checkout_and_sends_no_repo(self):
        row = self.ledgerRow()
        self.assertEqual(row["_cwd"], str(self.worktree.resolve()))
        self.assertNotIn("repo", row)

    def test_a_caller_repo_is_never_sent(self):
        self.assertNotIn("repo", self.ledgerRow("repo=wt-some-branch"))

    def test_the_branch_is_sent_as_branch_key_and_the_result_with_underscores(self):
        row = self.ledgerRow("result=PASS WITH WARNINGS")
        self.assertEqual((row["branch_key"], row["result"]), ("some-branch", "PASS_WITH_WARNINGS"))
        self.assertNotIn("branch", row)

    def test_leading_tilde_slash_expands_to_home(self):
        homeLogPath = self.home / "x"
        self.loggedMetricsRowAt("~/x", homeLogPath)

    def test_tilde_user_is_not_expanded(self):
        tildeUserDir = self.worktree / "~user"
        tildeUserDir.mkdir()
        tildeUserLogPath = tildeUserDir / "x"
        self.loggedMetricsRowAt("~user/x", tildeUserLogPath)

    def test_tilde_inside_a_path_is_literal(self):
        tildeInNameLogPath = self.root / "a~b.jsonl"
        self.loggedMetricsRowAt(tildeInNameLogPath, tildeInNameLogPath)

    def test_bare_tilde_expands_to_home_directory_and_exits_nonzero(self):
        metricsRun = self.runMetrics("out=~", "iter=7")
        self.assertNotEqual(metricsRun.returncode, 0)


if __name__ == "__main__":
    unittest.main()
