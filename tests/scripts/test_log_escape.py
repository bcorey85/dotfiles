"""Checks for log-escape: it writes one review_escape row through `ledger write`.

A stand-in `ledger` (fake_ledger) records what the script sends. Every case runs in a temp git repo with HOME
set to a temp dir, so nothing reaches a real log.

Script location: LOG_ESCAPE_SCRIPT, defaulting to ~/.claude/scripts/telemetry/log-escape.
"""
import os
import pathlib
import subprocess
import tempfile
import unittest

import fake_ledger
import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("LOG_ESCAPE_SCRIPT") or toolkit_paths.TELEMETRY_DIR / "log-escape")

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.com", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}

PLANTED_BRANCH = "planted-branch-zq"
VALID_ARGS = ["gate_missed=review", "stage_found=pr-human", "severity=high", "class=bug", "guard=none"]


class LogEscapeTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_root = pathlib.Path(temp_dir.name).resolve()
        self.home = self.temp_root / "home"
        (self.home / ".claude").mkdir(parents=True)
        self.ledger_env = fake_ledger.install(self.temp_root)
        self.repo = self.temp_root / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", PLANTED_BRANCH)
        (self.repo / "kept.txt").write_text("one\n")
        self.git("add", "kept.txt")
        self.git("commit", "-q", "-m", "base")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, env={**os.environ, **GIT_ENV}, check=True,
                              capture_output=True, text=True).stdout.strip()

    def environment(self, **extra):
        caller_env = {key: value for key, value in os.environ.items()
                     if key not in ("CLAUDE_TOOLKIT_TELEMETRY", "CLAUDE_CODE_SESSION_ID")}
        return {**caller_env, **GIT_ENV, **self.ledger_env, "HOME": str(self.home),
                "CLAUDE_TOOLKIT_TELEMETRY": "1", **extra}

    def run_escape(self, *args, env=None):
        return subprocess.run(["bash", str(SCRIPT), *args], cwd=self.repo, env=env or self.environment(),
                              capture_output=True, text=True)

    def escape_rows(self):
        return fake_ledger.recorded_rows(self.ledger_env, "review_escape")

    def test_writes_review_escape_with_string_values(self):
        done = self.run_escape(*VALID_ARGS, "line=7", "lane=code")
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))
        rows = self.escape_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["gate_missed"], "review")
        self.assertEqual(rows[0]["line"], "7")
        for field in ("date", "schema_version", "repo", "session"):
            self.assertNotIn(field, rows[0])

    def test_drops_desc_and_scan_flagged(self):
        done = self.run_escape(*VALID_ARGS, "desc=planted description zq", "scan_flagged=1")
        self.assertEqual(done.returncode, 0, done.stderr)
        row = self.escape_rows()[0]
        self.assertNotIn("desc", row)
        self.assertNotIn("scan_flagged", row)

    def test_renames_file_and_branch_to_keyed_fields(self):
        done = self.run_escape(*VALID_ARGS, "file=src/planted_widget_zq.rs", "branch=caller-branch")
        self.assertEqual(done.returncode, 0, done.stderr)
        row = self.escape_rows()[0]
        self.assertEqual(row["path_key"], "src/planted_widget_zq.rs")
        self.assertEqual(row["branch_key"], "caller-branch")
        self.assertNotIn("file", row)
        self.assertNotIn("branch", row)

    def test_seeds_head_and_branch_from_git(self):
        done = self.run_escape(*VALID_ARGS)
        self.assertEqual(done.returncode, 0, done.stderr)
        row = self.escape_rows()[0]
        self.assertEqual(row["head"], self.git("rev-parse", "HEAD"))
        self.assertEqual(row["branch_key"], PLANTED_BRANCH)

    def test_caller_branch_wins(self):
        done = self.run_escape(*VALID_ARGS, "branch=caller-branch")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.escape_rows()[0]["branch_key"], "caller-branch")

    def test_space_in_a_non_free_value_is_refused(self):
        done = self.run_escape(*VALID_ARGS, "lane=two words")
        self.assertEqual(done.returncode, 1)
        self.assertIn("refusing to log: lane= contains a space: 'two words'", done.stderr)
        self.assertEqual(self.escape_rows(), [])

    def test_pairs_in_one_unsplit_argument_are_folded_one_by_one(self):
        # zsh does not split an unquoted variable: C="gate_missed=review severity=high"; log-escape $C
        # sends one argument.
        done = self.run_escape("gate_missed=review stage_found=pr-human  severity=high", "class=bug", "guard=none")
        self.assertEqual(done.returncode, 0, done.stderr)
        row = self.escape_rows()[0]
        self.assertEqual((row["gate_missed"], row["stage_found"], row["severity"]), ("review", "pr-human", "high"))

    def test_a_spaced_value_with_a_bare_word_after_a_pair_is_refused(self):
        done = self.run_escape(*VALID_ARGS, "lane=code line=7 extra")
        self.assertEqual(done.returncode, 1)
        self.assertIn("refusing to log: lane= contains a space", done.stderr)
        self.assertEqual(self.escape_rows(), [])

    def test_file_with_a_swallowed_pair_is_refused(self):
        swallowing = ("a.py lane=code", "a.py\tlane=code", "a.py\nb.py", "a.py\rb.py")
        for path in swallowing:
            with self.subTest(path=path):
                done = self.run_escape(*VALID_ARGS, f"file={path}")
                self.assertEqual(done.returncode, 1)
                self.assertIn("refusing to log: file= holds a line break or whitespace then a name=", done.stderr)
                self.assertIn("Quote each key=value separately", done.stderr)
        self.assertEqual(self.escape_rows(), [])
        done = self.run_escape(*VALID_ARGS, "file=src/my dir/a b.py")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.escape_rows()[0]["path_key"], "src/my dir/a b.py")

    def test_desc_with_spaces_is_accepted_and_dropped(self):
        done = self.run_escape(*VALID_ARGS, "desc=free text, with spaces")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("desc", self.escape_rows()[0])

    def test_missing_guard_is_refused_with_the_ratchet_pointer(self):
        args = [argument for argument in VALID_ARGS if argument != "guard=none"]
        done = self.run_escape(*args)
        self.assertEqual(done.returncode, 1)
        self.assertIn("refusing to log: guard= is required.", done.stderr)
        self.assertIn("escape-ratchet.md", done.stderr)
        self.assertEqual(self.escape_rows(), [])

    def test_unknown_class_reaches_the_ledger(self):
        args = [argument.replace("class=bug", "class=nonsense") for argument in VALID_ARGS]
        done = self.run_escape(*args)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.escape_rows()[0]["class"], "nonsense")

    def test_unknown_guard_reaches_the_ledger_as_given(self):
        args = [argument.replace("guard=none", "guard=vibes") for argument in VALID_ARGS]
        done = self.run_escape(*args)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.escape_rows()[0]["guard"], "vibes")

    def test_check_writes_nothing(self):
        done = self.run_escape("--check", *VALID_ARGS)
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))
        self.assertEqual(self.escape_rows(), [])

    def test_telemetry_off_writes_nothing(self):
        done = self.run_escape(*VALID_ARGS, env=self.environment(CLAUDE_TOOLKIT_TELEMETRY="0"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout, "not logged: toolkit telemetry is off\n")
        self.assertEqual(self.escape_rows(), [])

    def test_ledger_exit_code_passes_through(self):
        for code in (2, 1):
            with self.subTest(code=code):
                done = self.run_escape(*VALID_ARGS, env=self.environment(FAKE_LEDGER_WRITE_EXIT=str(code)))
                self.assertEqual(done.returncode, code, done.stderr)
        self.assertEqual(self.escape_rows(), [])

    def test_retired_escapes_file_var_writes_no_file(self):
        retired = self.temp_root / "retired-escapes.jsonl"
        done = self.run_escape(*VALID_ARGS, env=self.environment(REVIEW_ESCAPES_FILE=str(retired)))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse(retired.exists())
        self.assertFalse((self.home / ".claude" / "review-escapes.jsonl").exists())
        self.assertEqual(len(self.escape_rows()), 1)


if __name__ == "__main__":
    unittest.main()
