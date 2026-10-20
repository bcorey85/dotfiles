"""Checks for calibration-refs-guard.py, the PostToolUse hook that reports reviewer agents naming calibration
headings that no longer exist."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or pathlib.Path.home() / ".claude" / "scripts")
SCRIPT = SCRIPTS_DIR / "calibration-refs-guard.py"

CALIBRATION = "# Calibration\n\n## Severity Scale\ntext\n\n## False Positives\ntext\n"
TAIL = ("A reviewer told to adopt a heading that does not exist gets that section only by\n"
        "accident, through \"adopt in full\". Update every agent that names the heading, or\n"
        "restore the heading, before moving on.\n")


class CalibrationRefsGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.home = self.root / "home"
        self.agents = self.root / "agents"
        self.agents.mkdir()
        self.home.mkdir()
        self.calibration = self.root / "shared" / "reviewer-calibration.md"
        self.calibration.parent.mkdir()
        self.calibration.write_text(CALIBRATION)

    def agent(self, name, content):
        path = self.agents / name
        path.write_text(content)
        return str(path)

    def run_hook(self, stdin, env=None):
        environment = {"PATH": os.environ["PATH"], "HOME": str(self.home), "TMPDIR": self.tmp.name,
                       "CALIB_FILE": str(self.calibration), "CALIB_AGENTS_DIR": str(self.agents)}
        environment.update(env or {})
        return subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True,
                              env=environment)

    def edit(self, path, env=None):
        finished = self.run_hook(json.dumps({"tool_name": "Edit", "tool_input": {"file_path": path}}), env)
        self.assertEqual((finished.returncode, finished.stderr), (0, ""))
        return finished.stdout

    def report(self, missing):
        return "⚠️  Reviewer calibration references are out of sync.\n\n" + missing + "\n" + TAIL

    def test_invalid_input_and_unwatched_paths_pass(self):
        for stdin in ("not json", "", json.dumps({"tool_input": {}})):
            finished = self.run_hook(stdin)
            self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, "", ""))
        path = self.agent("coder.md", "Adopt **Nope** from reviewer-calibration.md\n")
        self.assertEqual(self.edit(path), "")
        self.assertEqual(self.edit(str(self.root / "other" / "notes.md")), "")

    def test_in_sync_agents_are_silent(self):
        path = self.agent("code-reviewer.md", "First action: adopt its **Severity Scale**, **False Positives** from "
                                              "reviewer-calibration.md.\n")
        self.assertEqual(self.edit(path), "")

    def test_renamed_heading_is_reported_for_each_agent(self):
        self.agent("code-reviewer.md", "Read reviewer-calibration.md: adopt **Severity Scale**, **Old Name**.\n")
        path = self.agent("test-reviewer.md", "x\nreviewer-calibration.md **Gone Heading** and **Severity Scale**\n")
        self.agent("coder.md", "reviewer-calibration.md **Not Scanned**\n")
        self.assertEqual(self.edit(path), self.report(
            "  code-reviewer.md names \"Old Name\" — no such heading in the calibration file\n"
            "  test-reviewer.md names \"Gone Heading\" — no such heading in the calibration file\n"))

    def test_editing_the_calibration_file_triggers_the_scan(self):
        self.agent("code-reviewer.md", "reviewer-calibration.md **Old Name**\n")
        self.assertIn("Old Name", self.edit(str(self.calibration)))

    def test_only_lines_naming_the_calibration_file_are_scanned(self):
        path = self.agent("code-reviewer.md", "Use **Bold Elsewhere** here.\nreviewer-calibration.md plain\n")
        self.assertEqual(self.edit(path), "")

    def test_heading_match_is_case_insensitive_substring(self):
        path = self.agent("code-reviewer.md", "reviewer-calibration.md **severity scale** **False**\n")
        self.assertEqual(self.edit(path), "")

    def test_empty_bold_pair_is_ignored(self):
        path = self.agent("code-reviewer.md", "reviewer-calibration.md **** done\n")
        self.assertEqual(self.edit(path), "")

    def test_missing_calibration_file_passes(self):
        self.agent("code-reviewer.md", "reviewer-calibration.md **Old Name**\n")
        self.calibration.unlink()
        self.assertEqual(self.edit(str(self.agents / "code-reviewer.md")), "")

    def test_hidden_and_non_reviewer_files_are_not_scanned(self):
        self.agent(".hidden-reviewer.md", "reviewer-calibration.md **Old**\n")
        self.agent("reviewer.txt", "reviewer-calibration.md **Old**\n")
        path = self.agent("code-reviewer.md", "plain\n")
        self.assertEqual(self.edit(path), "")

    def test_default_paths_come_from_home(self):
        shared = self.home / ".claude" / "skills" / "_shared"
        agents = self.home / ".claude" / "agents"
        shared.mkdir(parents=True)
        agents.mkdir(parents=True)
        (shared / "reviewer-calibration.md").write_text(CALIBRATION)
        (agents / "x-reviewer.md").write_text("reviewer-calibration.md **Missing**\n")
        payload = json.dumps({"tool_input": {"file_path": str(agents / "x-reviewer.md")}})
        environment = {"PATH": os.environ["PATH"], "HOME": str(self.home)}
        finished = subprocess.run([sys.executable, str(SCRIPT)], input=payload, capture_output=True, text=True,
                                  env=environment)
        self.assertIn("x-reviewer.md names \"Missing\"", finished.stdout)


if __name__ == "__main__":
    unittest.main()
