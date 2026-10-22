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
SCRIPT = pathlib.Path(os.environ.get("LOG_SPEC_RUN_SCRIPT") or REAL_CLAUDE / "scripts" / "log-spec-run")
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

    def loggedSpecRunRow(self, *args):
        outFile = self.root / "never-written.jsonl"
        env = {**os.environ, **GIT_ENV, "HOME": str(self.home), **self.ledgerEnv}

        specRun = subprocess.run(
            [str(self.script), f"out={outFile}", "slug=my-plan", "verdict=finalized", "criteria=3", *args],
            env=env, cwd=self.worktree, capture_output=True, text=True,
        )
        self.assertEqual(specRun.returncode, 0, specRun.stderr)

        self.assertFalse(outFile.exists())

        specRunRows = fake_ledger.recorded_rows(self.ledgerEnv, "spec_run")
        self.assertEqual(len(specRunRows), 1)
        return specRunRows[0]

    def test_the_writer_runs_in_the_callers_checkout_and_sends_no_repo(self):
        specRunRow = self.loggedSpecRunRow()
        self.assertEqual(specRunRow["_cwd"], str(self.worktree.resolve()))
        self.assertNotIn("repo", specRunRow)

    def test_a_caller_repo_is_never_sent(self):
        self.assertNotIn("repo", self.loggedSpecRunRow("repo=wt-some-branch"))

    def test_slug_and_out_are_accepted_and_never_sent(self):
        specRunRow = self.loggedSpecRunRow()
        self.assertEqual((specRunRow["verdict"], specRunRow["criteria"]), ("finalized", "3"))
        self.assertNotIn("slug", specRunRow)
        self.assertNotIn("out", specRunRow)


if __name__ == "__main__":
    unittest.main()
