"""Checks for ledger-write and the metrics writers.

With a ledger found each writer's row goes to the ledger and no file is written. With no ledger found
(PATH, then `${CARGO_HOME:-~/.cargo}/bin`) the row is dropped: one stderr line, exit 0, no file. Every
case runs in a temp git repo with HOME and CARGO_HOME set to temp dirs.

Script location: LEDGER_WRITE_SCRIPT, defaulting to ~/.claude/scripts/telemetry/ledger-write.
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

LEDGER_WRITE = pathlib.Path(os.environ.get("LEDGER_WRITE_SCRIPT") or toolkit_paths.TELEMETRY_DIR / "ledger-write")
REVIEW_SKILL_DIR = toolkit_paths.CLAUDE_DIR / "skills" / "review"
SESSION = "session-under-test"
REPO_NAME = "planted-repo"
BRANCH = "planted-branch"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}

# One case per row type: the writer and its arguments.
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
    ),
    "review_run": (
        REVIEW_SKILL_DIR / "log-review-finding",
        ["kind=run", "gate=code-reviewer", "n_findings=2", "lane=none"],
    ),
    "review_metrics": (
        REVIEW_SKILL_DIR / "log-review-metrics",
        ["iter=2", "result=PASS WITH WARNINGS"],
    ),
    "review_escape": (
        toolkit_paths.TELEMETRY_DIR / "log-escape",
        ["gate_missed=review", "stage_found=pr-human", "severity=high", "class=bug", "guard=none"],
    ),
    "spec_run": (
        toolkit_paths.TELEMETRY_DIR / "log-spec-run",
        ["slug=my-plan", "verdict=finalized", "criteria=3"],
    ),
    "scan_run": (
        toolkit_paths.TELEMETRY_DIR / "log-scan",
        ["scan=prohibition", "stage=manual", "exit=0", "candidates=2", "confirmed=1"],
    ),
    "review_scope": (
        REVIEW_SKILL_DIR / "review-scope",
        ["caller=code", "skill=review"],
    ),
}
SWITCHED_WRITERS = ("review_escape", "scan_run", "spec_run", "review_metrics")


class LedgerWriteTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_root = pathlib.Path(temp_dir.name).resolve()
        self.home = self.temp_root / "home"
        self.home.mkdir()
        self.repo = self.temp_root / REPO_NAME
        self.repo.mkdir()
        self.git("init", "-q", "-b", BRANCH)
        (self.repo / "kept.txt").write_text("one\n")
        self.git("add", "kept.txt")
        self.git("commit", "-q", "-m", "base")
        self.ledger_env = fake_ledger.install(self.temp_root)

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.repo, env={**os.environ, **GIT_ENV}, check=True, capture_output=True, text=True
        ).stdout.strip()

    def run_script(self, script, args, with_ledger=False, stdin=None, telemetry="1", extra_env=None):
        caller_env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("CLAUDE_", "REVIEW_", "SPEC_RUNS", "SCAN_RUNS", "SKILL_USAGE"))
        }
        env = {
            **caller_env,
            **GIT_ENV,
            "HOME": str(self.home),
            "CARGO_HOME": str(self.home / ".cargo"),
            "CLAUDE_TOOLKIT_TELEMETRY": telemetry,
            "CLAUDE_CODE_SESSION_ID": SESSION,
            **(extra_env or {}),
        }
        if with_ledger:
            env["PATH"] = self.ledger_env["PATH"]
            env["FAKE_LEDGER_ROWS"] = self.ledger_env["FAKE_LEDGER_ROWS"]
        else:
            env["PATH"] = fake_ledger.path_without_ledger(os.environ["PATH"])
            self.assertIsNone(shutil.which("ledger", path=env["PATH"]))
        return subprocess.run(
            ["bash", str(script), *args], cwd=self.repo, env=env, capture_output=True, text=True, input=stdin
        )

    def files_written(self):
        return sorted(str(path) for path in self.temp_root.rglob("*.jsonl") if path.name != "fake-ledger-rows.jsonl")

    def test_no_ledger_drops_the_row_with_one_stderr_line_exit_0_and_no_file(self):
        for row_type, (script, args) in CASES.items():
            with self.subTest(row_type=row_type):
                done = self.run_script(script, args)
                self.assertEqual(done.returncode, 0, done.stderr)
                stderr_lines = [line for line in done.stderr.splitlines() if line.startswith("ledger-write:")]
                self.assertEqual(len(stderr_lines), 1, done.stderr)
                self.assertIn(f"no ledger found; {row_type} row dropped", stderr_lines[0])
                self.assertEqual(self.files_written(), [])
                self.assertFalse((self.home / ".claude").exists(), "a file or folder was made under HOME/.claude")

    def test_no_ledger_with_a_slow_producer_still_exits_0_under_pipefail(self):
        env = {
            **os.environ,
            "PATH": fake_ledger.path_without_ledger(os.environ["PATH"]),
            "HOME": str(self.home),
            "CARGO_HOME": str(self.home / ".cargo"),
        }
        self.assertIsNone(shutil.which("ledger", path=env["PATH"]))
        pipeline = f"set -o pipefail; {{ sleep 0.3; printf '{{}}\\n'; }} | bash {LEDGER_WRITE} scan_run"
        done = subprocess.run(["bash", "-c", pipeline], cwd=self.repo, env=env, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        drop_lines = [line for line in done.stderr.splitlines() if line.startswith("ledger-write:")]
        self.assertEqual(len(drop_lines), 1, done.stderr)

    def test_with_the_ledger_the_row_goes_to_the_ledger_and_no_file_is_written(self):
        for row_type, (script, args) in CASES.items():
            with self.subTest(row_type=row_type):
                done = self.run_script(script, args, with_ledger=True)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertNotIn("no ledger found", done.stderr)
                self.assertEqual(len(fake_ledger.recorded_rows(self.ledger_env, row_type)), 1)
                self.assertEqual(self.files_written(), [])
                self.assertFalse((self.home / ".claude").exists(), "a file or folder was made under HOME/.claude")

    def test_a_ledger_in_the_cargo_bin_folder_gets_the_row_when_path_has_none(self):
        cargo_bin = self.home / ".cargo" / "bin"
        cargo_bin.mkdir(parents=True)
        fake_ledger_binary = shutil.which("ledger", path=self.ledger_env["PATH"])
        shutil.copy2(fake_ledger_binary, cargo_bin / "ledger")
        script, args = CASES["review_escape"]

        done = self.run_script(script, args, extra_env={"FAKE_LEDGER_ROWS": self.ledger_env["FAKE_LEDGER_ROWS"]})

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("no ledger found", done.stderr)
        self.assertEqual(len(fake_ledger.recorded_rows(self.ledger_env, "review_escape")), 1)
        self.assertEqual(self.files_written(), [])

    def test_a_deferred_review_loop_fix_row_is_logged_only_for_an_open_class_member(self):
        script, args = CASES["review_finding"]
        deferred_args = [arg for arg in args if not arg.startswith("actioned=")] + ["actioned=deferred"]
        sources = (("class", True), ("last-pass", False), ("fix-diff", False), ("round", False), ("", False))
        for source, logged in sources:
            with self.subTest(source=source):
                source_args = [f"source={source}"] if source else []
                done = self.run_script(script, [*deferred_args, *source_args], with_ledger=True)
                self.assertEqual(done.returncode == 0, logged, done.stderr)
                if not logged:
                    self.assertIn("defers only as an open class member", done.stderr)

    def test_telemetry_off_writes_nothing_and_telemetry_on_with_the_ledger_writes_one_row(self):
        for row_type in SWITCHED_WRITERS:
            script, args = CASES[row_type]
            with self.subTest(row_type=row_type):
                done = self.run_script(script, args, with_ledger=True, telemetry="0")
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(fake_ledger.recorded_rows(self.ledger_env, row_type), [])
                control = self.run_script(script, args, with_ledger=True, telemetry="1")
                self.assertEqual(control.returncode, 0, control.stderr)
                self.assertEqual(len(fake_ledger.recorded_rows(self.ledger_env, row_type)), 1)

    def test_a_spec_run_row_loses_its_slug_and_the_session_goes_to_the_ledger(self):
        script, args = CASES["spec_run"]
        self.run_script(script, args, with_ledger=True)
        (spec_run_row,) = fake_ledger.recorded_rows(self.ledger_env, "spec_run")
        self.assertNotIn("slug", json.dumps(spec_run_row))
        self.assertEqual(spec_run_row["_session"], SESSION)

    def test_the_ledger_owned_keys_are_dropped_before_the_row_is_sent(self):
        row = {"verdict": "finalized", "date": "x", "schema_version": 9, "repo": "r", "session": "s"}
        done = self.run_script(LEDGER_WRITE, ["spec_run"], with_ledger=True, stdin=json.dumps(row))
        self.assertEqual(done.returncode, 0, done.stderr)
        (sent_row,) = fake_ledger.recorded_rows(self.ledger_env, "spec_run")
        for dropped_key in ("date", "schema_version", "repo", "session"):
            self.assertNotIn(dropped_key, sent_row)
        self.assertEqual(sent_row["verdict"], "finalized")

    def test_help_prints_usage_and_writes_nothing(self):
        for flag in ("--help", "-h"):
            with self.subTest(flag=flag):
                done = self.run_script(LEDGER_WRITE, [flag], with_ledger=True, stdin='{"verdict":"finalized"}')
                self.assertEqual((done.returncode, done.stderr), (0, ""))
                self.assertIn("usage: ledger-write <type>", done.stdout)
                self.assertEqual(fake_ledger.recorded_rows(self.ledger_env), [])


if __name__ == "__main__":
    unittest.main()
