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
SCRIPT = pathlib.Path(os.environ.get("LOG_SPEC_RUN_SCRIPT") or REAL_CLAUDE / "scripts" / "telemetry" / "log-spec-run")
TELEMETRY_ENABLED_SCRIPT = pathlib.Path(
    os.environ.get("TELEMETRY_ENABLED_SCRIPT") or REAL_CLAUDE / "scripts" / "telemetry" / "telemetry_enabled.sh"
)
KV_SCRIPT = REAL_CLAUDE / "scripts" / "lib" / "_kv.sh"
LEDGER_WRITE_SCRIPT = REAL_CLAUDE / "scripts" / "telemetry" / "ledger-write"

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
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.root = pathlib.Path(temp_dir.name)
        self.home = self.root / "home"
        (self.home / ".claude").mkdir(parents=True)
        (self.home / ".claude" / "toolkit-telemetry").touch()
        self.scripts_dir = self.root / "claude" / "scripts"
        telemetry_dir = self.scripts_dir / "telemetry"
        telemetry_dir.mkdir(parents=True)
        (self.scripts_dir / "lib").mkdir()
        self.script = telemetry_dir / "log-spec-run"
        shutil.copy2(SCRIPT, self.script)
        shutil.copy2(TELEMETRY_ENABLED_SCRIPT, telemetry_dir / "telemetry_enabled.sh")
        shutil.copy2(KV_SCRIPT, self.scripts_dir / "lib" / "_kv.sh")
        shutil.copy2(LEDGER_WRITE_SCRIPT, telemetry_dir / "ledger-write")
        self.ledger_env = fake_ledger.install(self.root)

        self.main_repo = self.root / "mainrepo"
        self.main_repo.mkdir()
        self.git(self.main_repo, "init", "-q")
        (self.main_repo / "README.md").write_text("hello\n", encoding="utf-8")
        self.git(self.main_repo, "add", "README.md")
        self.git(self.main_repo, "commit", "-q", "-m", "init")
        self.worktree = self.root / "wt-some-branch"
        self.git(self.main_repo, "worktree", "add", "-q", "-b", "some-branch", str(self.worktree))

    def git(self, cwd, *args):
        env = {**os.environ, **GIT_ENV}
        return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout

    def logged_spec_run_row(self, *args):
        out_file = self.root / "never-written.jsonl"
        env = {**os.environ, **GIT_ENV, "HOME": str(self.home), **self.ledger_env}

        spec_run = subprocess.run(
            [str(self.script), f"out={out_file}", "slug=my-plan", "verdict=finalized", "criteria=3", *args],
            env=env, cwd=self.worktree, capture_output=True, text=True,
        )
        self.assertEqual(spec_run.returncode, 0, spec_run.stderr)

        self.assertFalse(out_file.exists())

        spec_run_rows = fake_ledger.recorded_rows(self.ledger_env, "spec_run")
        self.assertEqual(len(spec_run_rows), 1)
        return spec_run_rows[0]

    def test_the_writer_runs_in_the_callers_checkout_and_sends_no_repo(self):
        spec_run_row = self.logged_spec_run_row()
        self.assertEqual(spec_run_row["_cwd"], str(self.worktree.resolve()))
        self.assertNotIn("repo", spec_run_row)

    def test_a_caller_repo_is_never_sent(self):
        self.assertNotIn("repo", self.logged_spec_run_row("repo=wt-some-branch"))

    def test_slug_and_out_are_accepted_and_never_sent(self):
        spec_run_row = self.logged_spec_run_row()
        self.assertEqual((spec_run_row["verdict"], spec_run_row["criteria"]), ("finalized", "3"))
        self.assertNotIn("slug", spec_run_row)
        self.assertNotIn("out", spec_run_row)


if __name__ == "__main__":
    unittest.main()
