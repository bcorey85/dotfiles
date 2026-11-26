"""Checks for code/phase_change_file.py: the phase-end run of the repo's change-file check."""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("PHASE_CHANGE_FILE_SCRIPT")
                      or toolkit_paths.CODE_DIR / "phase_change_file.py")
CHECK_SOURCE = toolkit_paths.REPO_ROOT / ".githooks" / "change-file-check"
TOOLKIT_FILE = "claude/.claude/scripts/lib/util.py"
CHANGE_NOTE = "docs/changes/notes/2026-11-25-a-change.md"
NEXT_STEP_LINE = ("Dispatch a coder to file the change file with that command, "
                  "then run phase_change_file.py again.")


class PhaseChangeFileTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.repo = pathlib.Path(scratch.name)
        self.git("init", "-q")
        self.write("README.md", "seed\n")
        self.git("add", "README.md")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "seed")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True, text=True)

    def write(self, relative_path, text="x\n"):
        target = self.repo / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def install_check(self):
        target = self.repo / ".githooks" / "change-file-check"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(CHECK_SOURCE, target)

    def run_script(self):
        return subprocess.run([sys.executable, str(SCRIPT)], cwd=self.repo, capture_output=True, text=True)

    def test_an_untracked_toolkit_file_without_a_change_note_fails_naming_the_path(self):
        self.install_check()
        self.write(TOOLKIT_FILE)
        result = self.run_script()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(TOOLKIT_FILE, result.stderr)
        self.assertIn("build_changes.py new", result.stderr)
        self.assertEqual(result.stderr.strip().splitlines()[-1], NEXT_STEP_LINE)

    def test_an_untracked_toolkit_path_that_git_would_quote_still_fails_naming_the_real_path(self):
        quoted_paths = [
            "claude/.claude/skills/café/SKILL.md",
            "claude/.claude/skills/tab\tname/SKILL.md",
            "claude/.claude/skills/new\nline/SKILL.md",
            'claude/.claude/skills/quote"name/SKILL.md',
        ]
        for toolkit_path in quoted_paths:
            with self.subTest(toolkit_path=toolkit_path):
                self.install_check()
                self.write(toolkit_path)
                result = self.run_script()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(toolkit_path, result.stderr)
                (self.repo / toolkit_path).unlink()

    def test_a_modified_tracked_toolkit_file_without_a_change_note_fails(self):
        self.write(TOOLKIT_FILE)
        self.git("add", TOOLKIT_FILE)
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "toolkit")
        self.install_check()
        self.write(TOOLKIT_FILE, "changed\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(TOOLKIT_FILE, result.stderr)

    def test_a_modified_tracked_toolkit_path_that_git_would_quote_fails_naming_the_real_path(self):
        quoted_paths = [
            "claude/.claude/skills/café/SKILL.md",
            "claude/.claude/skills/tab\tname/SKILL.md",
            "claude/.claude/skills/new\nline/SKILL.md",
            'claude/.claude/skills/quote"name/SKILL.md',
            "claude/.claude/skills/back\\slash/SKILL.md",
        ]
        for toolkit_path in quoted_paths:
            with self.subTest(toolkit_path=toolkit_path):
                self.write(toolkit_path)
                self.git("add", toolkit_path)
                self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "toolkit")
                self.install_check()
                self.write(toolkit_path, "changed\n")
                result = self.run_script()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(toolkit_path, result.stderr)
                self.git("checkout", "--", toolkit_path)

    def test_a_staged_rename_into_a_toolkit_path_fails_naming_the_new_path(self):
        renamed_path = "claude/.claude/skills/x/SKILL.md"
        (self.repo / renamed_path).parent.mkdir(parents=True)
        self.git("mv", "README.md", renamed_path)
        self.install_check()
        result = self.run_script()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(renamed_path, result.stderr)

    def test_an_untracked_change_note_passes(self):
        self.install_check()
        self.write(TOOLKIT_FILE)
        self.write(CHANGE_NOTE)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_repo_without_the_check_passes(self):
        self.write(TOOLKIT_FILE)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no change-file check in this repo", result.stdout)

    def test_a_change_outside_the_toolkit_passes(self):
        self.install_check()
        self.write("README.md", "edited\n")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_deleted_change_note_does_not_satisfy_the_check(self):
        self.write(CHANGE_NOTE)
        self.git("add", CHANGE_NOTE)
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "note")
        self.install_check()
        (self.repo / CHANGE_NOTE).unlink()
        self.write(TOOLKIT_FILE)
        result = self.run_script()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(TOOLKIT_FILE, result.stderr)

    def test_a_note_outside_the_pattern_does_not_satisfy_the_check(self):
        self.install_check()
        self.write(TOOLKIT_FILE)
        self.write("docs/changes/notes/draft.md")
        result = self.run_script()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(TOOLKIT_FILE, result.stderr)

    def test_a_stream_with_a_bad_status_exits_2_naming_the_expected_form(self):
        self.install_check()
        check = self.repo / ".githooks" / "change-file-check"
        result = subprocess.run([str(check)], input="AM\0some/path\0", capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("change-file-check:", result.stderr)
        self.assertIn("capital status letter", result.stderr)

    def test_a_stream_that_is_not_nul_terminated_status_path_pairs_exits_2(self):
        self.install_check()
        check = self.repo / ".githooks" / "change-file-check"
        bad_streams = {
            "newline form": "M\tclaude/.claude/skills/x/SKILL.md\n",
            "path with no closing NUL": "M\0claude/.claude/skills/x/SKILL.md",
            "status with no path": "A\0claude/.claude/scripts/lib/x.py\0M\0",
            "status with no NUL": "A\0claude/.claude/scripts/lib/x.py\0A",
        }
        for label, stream in bad_streams.items():
            with self.subTest(label=label):
                result = subprocess.run([str(check)], input=stream, capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("change-file-check: stdin:", result.stderr)

    def test_the_refusal_text_names_the_change_set(self):
        self.install_check()
        self.write(TOOLKIT_FILE)
        result = self.run_script()
        self.assertIn("change-file-check: the change set changes the toolkit but adds or modifies no "
                      "docs/changes/notes/20*.md file:", result.stderr)

    def test_a_check_that_crashes_exits_2_without_the_next_step_line(self):
        self.install_check()
        check = self.repo / ".githooks" / "change-file-check"
        check.write_text("#!/usr/bin/env bash\nexit 2\n", encoding="utf-8")
        result = self.run_script()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertNotIn(NEXT_STEP_LINE, result.stderr)


if __name__ == "__main__":
    unittest.main()
