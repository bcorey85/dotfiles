"""Checks for ledger-write and the metrics writers when no `ledger` is on PATH.

Each writer appends its row to the jsonl file its type used before the ledger, with date, schema_version,
repo and session added, and prints one stderr line. With the ledger present the row goes to the ledger
and no file is written. Every case runs in a temp git repo with HOME set to a temp dir.

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

# One case per row type: the writer, its arguments, the file and the fields the appended row must hold.
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
        {"kind": "finding", "branch": BRANCH},
    ),
    "review_run": (
        REVIEW_SKILL_DIR / "log-review-finding",
        ["kind=run", "gate=code-reviewer", "n_findings=2", "lane=none"],
        "review-findings.jsonl",
        {"kind": "run", "branch": BRANCH},
    ),
    "review_metrics": (
        REVIEW_SKILL_DIR / "log-review-metrics",
        ["iter=2", "result=PASS WITH WARNINGS"],
        "review-metrics.jsonl",
        {"iter": 2, "branch": BRANCH, "result": "PASS WITH WARNINGS"},
    ),
    "review_escape": (
        toolkit_paths.TELEMETRY_DIR / "log-escape",
        ["gate_missed=review", "stage_found=pr-human", "severity=high", "class=bug", "guard=none"],
        "review-escapes.jsonl",
        {"class": "bug", "branch": BRANCH},
    ),
    "spec_run": (
        toolkit_paths.TELEMETRY_DIR / "log-spec-run",
        ["slug=my-plan", "verdict=finalized", "criteria=3"],
        "spec-runs.jsonl",
        {"criteria": 3},
    ),
    "scan_run": (
        toolkit_paths.TELEMETRY_DIR / "log-scan",
        ["scan=prohibition", "stage=manual", "exit=0", "candidates=2", "confirmed=1"],
        "scan-runs.jsonl",
        {"candidates": 2},
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

    def run_script(self, script, args, with_ledger=False, stdin=None, telemetry="1", extra_env=None, home_set=True):
        caller_env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("CLAUDE_", "REVIEW_", "SPEC_RUNS", "SCAN_RUNS", "SKILL_USAGE"))
        }
        env = {
            **caller_env,
            **GIT_ENV,
            "HOME": str(self.home),
            "CLAUDE_TOOLKIT_TELEMETRY": telemetry,
            "CLAUDE_CODE_SESSION_ID": SESSION,
            **(extra_env or {}),
        }
        if not home_set:
            del env["HOME"]
        if with_ledger:
            env["PATH"] = self.ledger_env["PATH"]
            env["FAKE_LEDGER_ROWS"] = self.ledger_env["FAKE_LEDGER_ROWS"]
        else:
            env["PATH"] = fake_ledger.path_without_ledger(os.environ["PATH"])
            self.assertIsNone(shutil.which("ledger", path=env["PATH"]))
        return subprocess.run(
            ["bash", str(script), *args], cwd=self.repo, env=env, capture_output=True, text=True, input=stdin
        )

    def logged_rows(self, file_name):
        log_path = self.home / ".claude" / file_name
        return [json.loads(line) for line in log_path.read_text().splitlines()]

    def test_no_ledger_appends_the_completed_row_to_the_type_file_and_prints_one_stderr_line(self):
        for row_type, (script, args, file_name, expected_fields) in CASES.items():
            with self.subTest(row_type=row_type):
                done = self.run_script(script, args)
                self.assertEqual(done.returncode, 0, done.stderr)
                appended_row = self.logged_rows(file_name)[-1]
                for field, value in expected_fields.items():
                    self.assertEqual(appended_row[field], value, field)
                self.assertTrue(appended_row["date"].endswith("Z"), appended_row["date"])
                self.assertEqual((appended_row["repo"], appended_row["session"]), (REPO_NAME, SESSION))
                self.assertIsInstance(appended_row["schema_version"], int)
                stderr_lines = done.stderr.strip().splitlines()
                self.assertEqual(len(stderr_lines), 1, done.stderr)
                log_path = self.home / ".claude" / file_name
                self.assertIn(f"ledger not on PATH; row appended to {log_path}", stderr_lines[0])

    def test_with_the_ledger_the_row_goes_to_the_ledger_and_no_file_is_written(self):
        for row_type, (script, args, file_name, _expected_fields) in CASES.items():
            with self.subTest(row_type=row_type):
                done = self.run_script(script, args, with_ledger=True)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertNotIn("ledger not on PATH", done.stderr)
                self.assertEqual(len(fake_ledger.recorded_rows(self.ledger_env, row_type)), 1)
                self.assertFalse((self.home / ".claude" / file_name).exists())

    def test_a_deferred_review_loop_fix_row_is_logged_only_for_an_open_class_member(self):
        script, args, _file_name, _expected_fields = CASES["review_finding"]
        deferred_args = [arg for arg in args if not arg.startswith("actioned=")] + ["actioned=deferred"]
        sources = (("class", True), ("last-pass", False), ("fix-diff", False), ("round", False), ("", False))
        for source, logged in sources:
            with self.subTest(source=source):
                source_args = [f"source={source}"] if source else []
                done = self.run_script(script, [*deferred_args, *source_args], with_ledger=True)
                self.assertEqual(done.returncode == 0, logged, done.stderr)
                if not logged:
                    self.assertIn("defers only as an open class member", done.stderr)

    def test_telemetry_off_writes_no_file_without_a_ledger(self):
        for row_type in SWITCHED_WRITERS:
            script, args, file_name, _expected_fields = CASES[row_type]
            with self.subTest(row_type=row_type):
                log_path = self.home / ".claude" / file_name
                done = self.run_script(script, args, telemetry="0")
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertFalse(log_path.exists())
                control = self.run_script(script, args, telemetry="1")
                self.assertEqual(control.returncode, 0, control.stderr)
                self.assertTrue(log_path.exists(), "the telemetry=1 control wrote no file")

    def test_each_file_override_receives_the_row_and_the_default_file_gets_nothing(self):
        file_overrides = {
            "review_finding": "REVIEW_FINDINGS_FILE",
            "review_run": "REVIEW_FINDINGS_FILE",
            "review_metrics": "REVIEW_METRICS_FILE",
            "review_escape": "REVIEW_ESCAPES_FILE",
            "spec_run": "SPEC_RUNS_FILE",
            "scan_run": "SCAN_RUNS_FILE",
        }
        for row_type, override_name in file_overrides.items():
            script, args, _file_name, _expected_fields = CASES[row_type]
            with self.subTest(row_type=row_type):
                override_path = self.temp_root / f"{row_type}-override.jsonl"
                done = self.run_script(script, args, extra_env={override_name: str(override_path)})
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(len(override_path.read_text().splitlines()), 1)
                self.assertFalse((self.home / ".claude").exists(), "the row also reached $HOME/.claude")

    def test_review_scope_skill_usage_override_receives_the_row(self):
        override_path = self.temp_root / "skill-usage-override.jsonl"
        done = self.run_script(
            REVIEW_SKILL_DIR / "review-scope",
            ["caller=code", "skill=review"],
            extra_env={"SKILL_USAGE_FILE": str(override_path)},
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(override_path.read_text().splitlines()), 1)
        self.assertFalse((self.home / ".claude").exists(), "the row also reached $HOME/.claude")

    def test_an_unset_home_drops_the_row_with_one_stderr_line_and_exits_0(self):
        done = self.run_script(LEDGER_WRITE, ["review_escape"], stdin='{"class":"bug"}', home_set=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stderr.strip(), "ledger-write: ledger not on PATH; HOME is unset, row dropped")

    def test_a_failed_append_prints_one_stderr_line_and_exits_0(self):
        script, args, _file_name, _expected_fields = CASES["review_escape"]
        (self.home / ".claude").write_text("a file where the directory should be\n")
        done = self.run_script(script, args)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(done.stderr.strip().splitlines()), 1, done.stderr)
        self.assertIn("could not append", done.stderr)
        self.assertIn("row dropped", done.stderr)

    def test_ids_and_the_head_commit_stay_strings_and_other_numbers_are_typed(self):
        row_text = json.dumps({"finding_id": "12e4567890123456", "run_id": "1234", "head": "1234567", "iter": "3"})
        done = self.run_script(LEDGER_WRITE, ["review_finding"], stdin=row_text)
        self.assertEqual(done.returncode, 0, done.stderr)
        appended_row = self.logged_rows("review-findings.jsonl")[-1]
        self.assertEqual(appended_row["finding_id"], "12e4567890123456")
        self.assertEqual((appended_row["run_id"], appended_row["head"]), ("1234", "1234567"))
        self.assertEqual(appended_row["iter"], 3)

    def test_numbers_inside_object_values_are_typed_and_dirty_and_a_dash_stay_strings(self):
        row_text = json.dumps(
            {
                "specialists": {"code_reviewer": "2", "name": "x"},
                "fixed_classes": {"bug": "1"},
                "dirty": "1",
                "phase": "-",
            }
        )
        done = self.run_script(LEDGER_WRITE, ["review_metrics"], stdin=row_text)
        self.assertEqual(done.returncode, 0, done.stderr)
        appended_row = self.logged_rows("review-metrics.jsonl")[-1]
        self.assertEqual(appended_row["specialists"], {"code_reviewer": 2, "name": "x"})
        self.assertEqual(appended_row["fixed_classes"], {"bug": 1})
        self.assertEqual((appended_row["dirty"], appended_row["phase"]), ("1", "-"))

    def test_only_the_three_underscore_results_are_spaced(self):
        for sent, stored in (
            ("PASS_WITH_WARNINGS", "PASS WITH WARNINGS"),
            ("NEEDS_CHANGES", "NEEDS CHANGES"),
            ("NOT_DISPATCHED", "NOT DISPATCHED"),
            ("PASS", "PASS"),
            ("some_other_value", "some_other_value"),
        ):
            with self.subTest(sent=sent):
                done = self.run_script(LEDGER_WRITE, ["review_metrics"], stdin=json.dumps({"result": sent}))
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(self.logged_rows("review-metrics.jsonl")[-1]["result"], stored)

    def test_a_spec_run_row_keeps_its_slug_without_a_ledger_and_loses_it_with_one(self):
        script, args, _file_name, _expected_fields = CASES["spec_run"]
        self.run_script(script, args)
        self.assertEqual(self.logged_rows("spec-runs.jsonl")[-1]["slug"], "my-plan")
        self.run_script(script, args, with_ledger=True)
        (spec_run_row,) = fake_ledger.recorded_rows(self.ledger_env, "spec_run")
        self.assertNotIn("slug", json.dumps(spec_run_row))

    def test_review_scope_falls_back_to_the_skill_usage_file_in_the_shape_it_always_held(self):
        done = self.run_script(REVIEW_SKILL_DIR / "review-scope", ["caller=code", "skill=review"])
        self.assertEqual(done.returncode, 0, done.stderr)
        appended_row = self.logged_rows("skill-usage.jsonl")[-1]
        self.assertEqual((appended_row["skill"], appended_row["caller"]), ("review", "code"))
        self.assertEqual((appended_row["repo"], appended_row["session"]), (REPO_NAME, SESSION))
        self.assertEqual(appended_row["via"], "agent")
        self.assertTrue(appended_row["ts"].endswith("Z"), appended_row["ts"])
        self.assertNotIn("date", appended_row)
        self.assertNotIn("schema_version", appended_row)
        writer_lines = [line for line in done.stderr.splitlines() if line.startswith("ledger-write:")]
        self.assertEqual(len(writer_lines), 1, done.stderr)


if __name__ == "__main__":
    unittest.main()
