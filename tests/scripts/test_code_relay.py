"""Tests for code_relay.py: the main session's word-for-word relay of the /code fork's last stop."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("CODE_RELAY_SCRIPT") or toolkit_paths.CODE_DIR / "code_relay.py")
STOP = "Phase 2 complete. Stopped for your review.\n\nTo go on: /code resume <your feedback>"


class RelayTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = pathlib.Path(folder.name)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.run_folder = self.repo / ".git" / "code-phase"

    def write_stop(self, text):
        self.run_folder.mkdir(exist_ok=True)
        (self.run_folder / "stop.md").write_text(text)

    def relay(self):
        return subprocess.run([sys.executable, str(SCRIPT)], cwd=self.repo, capture_output=True, text=True,
                              check=False)

    def test_a_new_stop_prints_word_for_word_between_markers_under_the_no_tool_rule(self):
        self.write_stop(STOP + "\n")

        result = self.relay()

        self.assertEqual(result.returncode, 0, result.stderr)
        rule, body = result.stdout.split("-----BEGIN USER TEXT-----\n")
        self.assertIn("Make no other tool call", rule)
        self.assertEqual(body, STOP + "\n-----END USER TEXT-----\n")

    def test_a_stop_relayed_already_exits_1_and_says_to_relay_the_skill_result(self):
        self.write_stop(STOP)
        self.relay()

        result = self.relay()

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("relayed already", result.stderr)
        self.assertIn("Skill result word for word", result.stderr)

    def test_a_rewritten_stop_relays_again(self):
        self.write_stop(STOP)
        self.relay()
        os.utime(self.run_folder / "stop.md", ns=(1, 1))

        result = self.relay()

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_stop_file_exits_1_and_says_to_relay_the_skill_result(self):
        result = self.relay()

        self.assertEqual(result.returncode, 1)
        self.assertIn("no stop file", result.stderr)


if __name__ == "__main__":
    unittest.main()
