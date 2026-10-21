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
SCRIPT = pathlib.Path(os.environ.get("LOG_SPEC_RUN_SCRIPT") or REAL_CLAUDE / "scripts" / "log-spec-run")
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


class LogSpecRunRepoTest(unittest.TestCase):
    def setUp(self):
        tempDir = tempfile.TemporaryDirectory()
        self.addCleanup(tempDir.cleanup)
        self.root = pathlib.Path(tempDir.name)
        self.home = self.root / "home"
        (self.home / ".claude").mkdir(parents=True)
        (self.home / ".claude" / "toolkit-telemetry").touch()
        self.scriptsDir = self.root / "claude" / "scripts"
        self.scriptsDir.mkdir(parents=True)
        self.script = self.scriptsDir / "log-spec-run"
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

    def loggedSpecRunRow(self, *args):
        self.callCount += 1
        outFile = self.root / f"out{self.callCount}.jsonl"
        env = {**os.environ, **GIT_ENV, "HOME": str(self.home)}
        env.pop("SPEC_RUNS_FILE", None)

        specRun = subprocess.run(
            [str(self.script), f"out={outFile}", "slug=my-plan", "verdict=finalized", "criteria=3", *args],
            env=env, cwd=self.worktree, capture_output=True, text=True,
        )
        self.assertEqual(specRun.returncode, 0, specRun.stderr)

        loggedLines = outFile.read_text().splitlines()
        self.assertEqual(len(loggedLines), 1)

        specRunRow = json.loads(loggedLines[0])
        self.assertEqual(specRunRow["slug"], "my-plan")
        return specRunRow

    def test_no_repo_arg_gets_main_repo_name_from_worktree(self):
        self.assertEqual(self.loggedSpecRunRow()["repo"], "mainrepo")

    def test_canonical_name_wins_over_caller_repo(self):
        self.assertEqual(self.loggedSpecRunRow("repo=wt-some-branch")["repo"], "mainrepo")

    def test_caller_repo_kept_when_repo_name_fails(self):
        self.useFailingRepoName()
        self.assertEqual(self.loggedSpecRunRow("repo=caller-repo")["repo"], "caller-repo")

    def test_no_repo_name_and_no_caller_repo_still_logs(self):
        self.useFailingRepoName()
        self.assertNotIn("repo", self.loggedSpecRunRow())


if __name__ == "__main__":
    unittest.main()
