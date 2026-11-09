"""Tests for phase_start.py, the record of the tree a /code phase starts from, and the held files code_review_start.py
reads from it. Set PHASE_START_SCRIPT to run against another copy."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

PHASE_START = pathlib.Path(os.environ.get("PHASE_START_SCRIPT") or toolkit_paths.CODE_DIR / "phase_start.py")
REVIEW_START = PHASE_START.parent / "code_review_start.py"
ENV = {**os.environ, "CLAUDE_CODE_SESSION_ID": "test-session"}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


class PhaseStartTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        scratch = pathlib.Path(folder.name).resolve()
        self.repo = scratch / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        for name in ("mine.py", "theirs.py", "shared.py"):
            (self.repo / name).write_text(f"# {name}\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "base")
        self.handoff = scratch / "handoff.txt"
        self.handoff.write_text("  files:\n    - path: mine.py\n      why: the phase change\n")

    def phase_start(self):
        return self.phase_start_with()

    def phase_start_with(self, *flags):
        return subprocess.run([sys.executable, str(PHASE_START), *flags], cwd=self.repo, capture_output=True,
                              text=True, check=False)

    def recorded_dirty(self):
        return sorted(json.loads((self.repo / ".git/code-phase/start.json").read_text())["dirty"])

    def test_a_second_phase_start_at_the_same_head_keeps_the_first_record(self):
        (self.repo / "theirs.py").write_text("# another session's edit\n")
        self.phase_start()
        (self.repo / "mine.py").write_text("# the first phase's file\n")

        done = self.phase_start()

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual(self.recorded_dirty(), ["theirs.py"])

    def test_new_run_replaces_the_record(self):
        (self.repo / "theirs.py").write_text("# another session's edit\n")
        self.phase_start()
        (self.repo / "mine.py").write_text("# a file dirty at the new run's start\n")

        done = self.phase_start_with("--new-run")

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.recorded_dirty(), ["mine.py", "theirs.py"])

    def test_a_moved_head_replaces_the_record(self):
        (self.repo / "theirs.py").write_text("# another session's edit\n")
        self.phase_start()
        git(self.repo, "commit", "-q", "-am", "next")
        (self.repo / "mine.py").write_text("# dirty after the commit\n")

        done = self.phase_start()

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.recorded_dirty(), ["mine.py"])

    def test_a_record_that_does_not_parse_is_replaced_with_a_note_naming_the_file(self):
        self.phase_start()
        record_file = self.repo / ".git/code-phase/start.json"
        record_file.write_text("{}")
        (self.repo / "theirs.py").write_text("# another session's edit\n")

        done = self.phase_start()

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn(str(record_file), done.stderr)
        self.assertEqual(self.recorded_dirty(), ["theirs.py"])

    def test_an_unknown_argument_stops_before_any_record_is_written(self):
        done = self.phase_start_with("--new_run")

        self.assertNotEqual(done.returncode, 0)
        self.assertIn("usage: phase_start.py [--new-run]", done.stderr)
        self.assertFalse((self.repo / ".git/code-phase/start.json").exists())

    def review_prompt(self, base):
        return subprocess.run([sys.executable, str(REVIEW_START), "lane-a", "-", "1", str(self.handoff), "--base", base,
                               "--dry-run"], cwd=self.repo, capture_output=True, text=True, check=False, env=ENV)

    def test_the_record_names_head_and_every_dirty_file_and_the_sha_is_printed(self):
        (self.repo / "theirs.py").write_text("# another session's edit\n")
        (self.repo / "new.txt").write_text("untracked\n")

        done = self.phase_start()

        self.assertEqual(done.returncode, 0, done.stderr)
        head = git(self.repo, "rev-parse", "HEAD")
        self.assertEqual(done.stdout.strip(), head)
        record = json.loads((self.repo / ".git/code-phase/start.json").read_text())
        self.assertEqual(record["head"], head)
        self.assertEqual(sorted(record["dirty"]), ["new.txt", "theirs.py"])

    def test_a_file_dirty_at_the_phase_start_with_the_same_bytes_is_held_out_of_the_review(self):
        (self.repo / "theirs.py").write_text("# another session's edit\n")
        (self.repo / "shared.py").write_text("# another session's edit\n")
        base = self.phase_start().stdout.strip()
        (self.repo / "mine.py").write_text("# the phase's coder\n")
        (self.repo / "shared.py").write_text("# the phase's coder edited it too\n")

        done = self.review_prompt(base)

        self.assertEqual(done.returncode, 0, done.stderr)
        header, _, handoff = done.stdout.partition("\n\n")
        self.assertIn("held files: theirs.py", header.splitlines())
        self.assertIn("- path: mine.py", handoff)
        self.assertIn("- path: shared.py", handoff)
        self.assertNotIn("theirs.py", handoff)

    def test_a_record_of_another_base_stops_the_review_start(self):
        self.phase_start()
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "next phase")

        done = self.review_prompt("HEAD")

        self.assertNotEqual(done.returncode, 0)
        self.assertIn("phase_start.py did not run before this phase's coder", done.stderr)

    def test_no_record_holds_no_file_and_says_so(self):
        (self.repo / "theirs.py").write_text("# another session's edit\n")

        done = self.review_prompt("HEAD")

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("held files:", done.stdout)
        self.assertIn("no phase start record", done.stderr)


if __name__ == "__main__":
    unittest.main()
