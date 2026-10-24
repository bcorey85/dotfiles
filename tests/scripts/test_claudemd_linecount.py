"""Checks for claudemd_linecount.py, the PostToolUse hook that warns when an edited CLAUDE.md passes 150 lines."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or toolkit_paths.SCRIPTS_DIR)
SCRIPT = SCRIPTS_DIR / "claudemd_linecount.py"

WARNING = "CLAUDE.md is %d lines (target: <150). Consider moving reference data to skills or MEMORY.md.\n"


class ClaudeMdLinecountTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "home").mkdir()

    def write(self, name, line_count):
        path = self.root / name
        path.write_text("line\n" * line_count)
        return str(path)

    def run_hook(self, stdin):
        environment = {"PATH": os.environ["PATH"], "HOME": str(self.root / "home"), "TMPDIR": self.tmp.name}
        return subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True,
                              env=environment)

    def edit(self, path):
        finished = self.run_hook(json.dumps({"tool_name": "Write", "tool_input": {"file_path": path}}))
        self.assertEqual((finished.returncode, finished.stdout), (0, ""))
        return finished.stderr

    def test_invalid_input_passes(self):
        for stdin in ("not json", "", json.dumps({"tool_input": {}}), json.dumps({"tool_input": {"file_path": ""}})):
            finished = self.run_hook(stdin)
            self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, "", ""))

    def test_over_limit_warns(self):
        self.assertEqual(self.edit(self.write("CLAUDE.md", 151)), WARNING % 151)

    def test_at_limit_is_silent(self):
        self.assertEqual(self.edit(self.write("CLAUDE.md", 150)), "")

    def test_name_match_is_case_insensitive_and_suffix_only(self):
        self.assertEqual(self.edit(self.write("project-claude.md", 200)), WARNING % 200)
        self.assertEqual(self.edit(self.write("CLAUDE.md.bak", 200)), "")
        self.assertEqual(self.edit(self.write("NOTES.md", 200)), "")

    def test_unterminated_last_line_is_not_counted(self):
        path = self.root / "CLAUDE.md"
        path.write_text("line\n" * 150 + "tail")
        self.assertEqual(self.edit(str(path)), "")

    def test_missing_claude_md_prints_one_plain_open_error(self):
        path = str(self.root / "gone" / "CLAUDE.md")
        stderr = self.edit(path)
        self.assertEqual(stderr, f"claudemd-linecount: cannot open {path}: No such file or directory\n")

    def test_skip_variable_does_not_disable_warning(self):
        path = self.write("CLAUDE.md", 160)
        environment = {"PATH": os.environ["PATH"], "HOME": str(self.root / "home"), "CLAUDE_SKIP_HOOKS": "1"}
        finished = subprocess.run([sys.executable, str(SCRIPT)],
                                  input=json.dumps({"tool_input": {"file_path": path}}), capture_output=True,
                                  text=True, env=environment)
        self.assertEqual(finished.stderr, WARNING % 160)


if __name__ == "__main__":
    unittest.main()
