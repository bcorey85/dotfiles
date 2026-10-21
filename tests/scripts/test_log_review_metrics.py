import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

os.environ.pop("CLAUDE_TOOLKIT_TELEMETRY", None)  # the switch file alone decides in these tests

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REAL_CLAUDE = REPO_ROOT / "claude" / ".claude"
SCRIPT = pathlib.Path(os.environ.get("LOG_REVIEW_METRICS_SCRIPT") or REAL_CLAUDE / "skills" / "review" / "log-review-metrics")
TELEMETRY_ENABLED_SCRIPT = pathlib.Path(os.environ.get("TELEMETRY_ENABLED_SCRIPT") or REAL_CLAUDE / "scripts" / "telemetry_enabled.sh")
REPO_NAME_SCRIPT = pathlib.Path(os.environ.get("REPO_NAME_SCRIPT") or REAL_CLAUDE / "scripts" / "repo-name")

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}

STUB_FAIL = "#!/usr/bin/env bash\nexit 1\n"


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
        shutil.copy2(REPO_NAME_SCRIPT, self.scriptsDir / "repo-name")
        shutil.copy2(TELEMETRY_ENABLED_SCRIPT, self.scriptsDir / "telemetry_enabled.sh")

        self.mainRepo = self.root / "mainrepo"
        self.mainRepo.mkdir()
        self.git(self.mainRepo, "init", "-q")
        (self.mainRepo / "README.md").write_text("hello\n", encoding="utf-8")
        self.git(self.mainRepo, "add", "README.md")
        self.git(self.mainRepo, "commit", "-q", "-m", "init")
        self.worktree = self.root / "wt-some-branch"
        self.git(self.mainRepo, "worktree", "add", "-q", "-b", "some-branch", str(self.worktree))
        self.callCount = 0

    def git(self, cwd, *args):
        env = {**os.environ, **GIT_ENV}
        return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout

    def useFailingRepoName(self):
        repoNamePath = self.scriptsDir / "repo-name"
        repoNamePath.write_text(STUB_FAIL, encoding="utf-8")
        repoNamePath.chmod(0o755)

    def runMetrics(self, *args):
        env = {**os.environ, **GIT_ENV, "HOME": str(self.home)}
        env.pop("REVIEW_METRICS_FILE", None)
        return subprocess.run([str(self.script), *args], env=env, cwd=self.worktree, capture_output=True, text=True)

    def loggedMetricsRowAt(self, outValue, expectedLogPath, *args):
        metricsRun = self.runMetrics(f"out={outValue}", "iter=7", *args)
        self.assertEqual(metricsRun.returncode, 0, metricsRun.stderr)

        loggedLines = expectedLogPath.read_text().splitlines()
        self.assertEqual(len(loggedLines), 1)

        metricsRow = json.loads(loggedLines[0])
        self.assertEqual(metricsRow["iter"], 7)
        return metricsRow

    def loggedMetricsRow(self, *args):
        self.callCount += 1
        outFile = self.root / f"out{self.callCount}.jsonl"
        return self.loggedMetricsRowAt(outFile, outFile, "result=PASS", *args)

    def test_no_repo_arg_gets_main_repo_name_from_worktree(self):
        self.assertEqual(self.loggedMetricsRow()["repo"], "mainrepo")

    def test_canonical_name_wins_over_caller_repo(self):
        self.assertEqual(self.loggedMetricsRow("repo=wt-some-branch")["repo"], "mainrepo")

    def test_caller_repo_kept_when_repo_name_fails(self):
        self.useFailingRepoName()
        self.assertEqual(self.loggedMetricsRow("repo=caller-repo")["repo"], "caller-repo")

    def test_no_repo_name_and_no_caller_repo_still_logs(self):
        self.useFailingRepoName()
        self.assertNotIn("repo", self.loggedMetricsRow())

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
