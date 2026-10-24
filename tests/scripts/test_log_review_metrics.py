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
SCRIPT = pathlib.Path(
    os.environ.get("LOG_REVIEW_METRICS_SCRIPT") or REAL_CLAUDE / "skills" / "review" / "log-review-metrics"
)
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


class LogReviewMetricsRepoTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.root = pathlib.Path(temp_dir.name)
        self.home = self.root / "home"
        (self.home / ".claude").mkdir(parents=True)
        (self.home / ".claude" / "toolkit-telemetry").touch()
        review_dir = self.root / "claude" / "skills" / "review"
        self.scripts_dir = self.root / "claude" / "scripts"
        review_dir.mkdir(parents=True)
        telemetry_dir = self.scripts_dir / "telemetry"
        telemetry_dir.mkdir(parents=True)
        (self.scripts_dir / "lib").mkdir()
        self.script = review_dir / "log-review-metrics"
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

    def run_metrics(self, *args):
        env = {**os.environ, **GIT_ENV, "HOME": str(self.home), **self.ledger_env}
        return subprocess.run([str(self.script), *args], env=env, cwd=self.worktree, capture_output=True, text=True)

    def logged_metrics_row_at(self, out_value, expected_log_path, *args):
        metrics_run = self.run_metrics(f"out={out_value}", "iter=7", *args)
        self.assertEqual(metrics_run.returncode, 0, metrics_run.stderr)

        logged_lines = expected_log_path.read_text().splitlines()
        self.assertEqual(len(logged_lines), 1)

        metrics_row = json.loads(logged_lines[0])
        self.assertEqual(metrics_row["iter"], "7")
        return metrics_row

    def ledger_row(self, *args):
        metrics_run = self.run_metrics("iter=7", "result=PASS", *args)
        self.assertEqual(metrics_run.returncode, 0, metrics_run.stderr)
        rows = fake_ledger.recorded_rows(self.ledger_env, "review_metrics")
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_the_writer_runs_in_the_callers_checkout_and_sends_no_repo(self):
        row = self.ledger_row()
        self.assertEqual(row["_cwd"], str(self.worktree.resolve()))
        self.assertNotIn("repo", row)

    def test_a_caller_repo_is_never_sent(self):
        self.assertNotIn("repo", self.ledger_row("repo=wt-some-branch"))

    def test_the_branch_is_sent_as_branch_key_and_the_result_with_underscores(self):
        row = self.ledger_row("result=PASS WITH WARNINGS")
        self.assertEqual((row["branch_key"], row["result"]), ("some-branch", "PASS_WITH_WARNINGS"))
        self.assertNotIn("branch", row)

    def test_leading_tilde_slash_expands_to_home(self):
        home_log_path = self.home / "x"
        self.logged_metrics_row_at("~/x", home_log_path)

    def test_tilde_user_is_not_expanded(self):
        tilde_user_dir = self.worktree / "~user"
        tilde_user_dir.mkdir()
        tilde_user_log_path = tilde_user_dir / "x"
        self.logged_metrics_row_at("~user/x", tilde_user_log_path)

    def test_tilde_inside_a_path_is_literal(self):
        tilde_in_name_log_path = self.root / "a~b.jsonl"
        self.logged_metrics_row_at(tilde_in_name_log_path, tilde_in_name_log_path)

    def test_bare_tilde_expands_to_home_directory_and_exits_nonzero(self):
        metrics_run = self.run_metrics("out=~", "iter=7")
        self.assertNotEqual(metrics_run.returncode, 0)


if __name__ == "__main__":
    unittest.main()
