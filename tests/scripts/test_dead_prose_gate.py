"""Checks for dead_prose_gate.py, the PostToolUse hook that warns on banned rationale and hardcoded paths in agent,
skill and command bodies. It never blocks."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or toolkit_paths.GATES_DIR)
SCRIPT = SCRIPTS_DIR / "dead_prose_gate.py"


class DeadProseGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "home").mkdir()

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return str(path)

    def run_hook(self, stdin):
        environment = {"PATH": os.environ["PATH"], "HOME": str(self.root / "home"), "TMPDIR": self.tmp.name}
        return subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True,
                              env=environment)

    def edit(self, path):
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": path}}
        finished = self.run_hook(json.dumps(payload))
        self.assertEqual(finished.returncode, 0)
        self.assertEqual(finished.stdout, "")
        return finished.stderr

    def test_invalid_input_and_missing_file_pass(self):
        for stdin in ("not json", "", json.dumps({"tool_input": {}}),
                      json.dumps({"tool_input": {"file_path": str(self.root / ".claude/agents/nope.md")}})):
            finished = self.run_hook(stdin)
            self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, "", ""))

    def test_files_outside_agent_skill_command_directories_pass(self):
        path = self.write("repo/docs/a.md", "This exists because of /home/me dotfiles 2026-01-02\n")
        self.assertEqual(self.edit(path), "")
        path = self.write(".claude/agents/a.txt", "/home/me\n")
        self.assertEqual(self.edit(path), "")

    def test_rationale_patterns_are_reported_for_agents_and_skills(self):
        samples = [
            "This exists because users asked",
            "it exists only because of X",
            "the reason this exists is Y",
            "a chosen budget, not a rule",
            "not a measured default",
            "chosen measured budget",
            "was retired in May",
            "retired because of cost",
            "measured basis here",
            "as measured",
            "we measured it",
            "see x 2026-08-09",
        ]
        for surface in ("agents", "skills/foo"):
            for sample in samples:
                with self.subTest(surface=surface, sample=sample):
                    path = self.write(f".claude/{surface}/a.md", f"keep this\n{sample}\nkeep that\n")
                    self.assertEqual(self.edit(path),
                                     "dead-prose-gate: possible banned rationale in a.md — the rule ships every "
                                     f"dispatch; keep the RULE, cut the defense:\n  2:{sample}\n")

    def test_rationale_is_case_insensitive_and_date_needs_a_leading_character(self):
        path = self.write(".claude/agents/a.md", "THIS EXISTS BECAUSE X\n2026-01-02 starts the line\n")
        self.assertEqual(self.edit(path),
                         "dead-prose-gate: possible banned rationale in a.md — the rule ships every dispatch; keep "
                         "the RULE, cut the defense:\n  1:THIS EXISTS BECAUSE X\n")

    def test_instructional_because_passes(self):
        path = self.write(".claude/skills/a.md", "Read in order, because step two needs step one.\n")
        self.assertEqual(self.edit(path), "")

    def test_commands_get_the_portability_check_only(self):
        path = self.write(".claude/commands/a.md", "This exists because of it\nsee /Users/me/x\n")
        self.assertEqual(self.edit(path),
                         "dead-prose-gate: hardcoded path or repo name in a.md — agents, skills and commands must "
                         "be portable across WSL/Ubuntu/macOS/Arch:\n  2:see /Users/me/x\n")

    def test_portability_patterns_are_reported(self):
        for sample in ("/Users/me/x", "/home/brandon/x", "in dotfiles repo"):
            with self.subTest(sample=sample):
                path = self.write(".claude/agents/a.md", f"ok\n{sample}\n")
                self.assertEqual(self.edit(path),
                                 "dead-prose-gate: hardcoded path or repo name in a.md — agents, skills and commands "
                                 f"must be portable across WSL/Ubuntu/macOS/Arch:\n  2:{sample}\n")

    def test_portability_ignores_embedded_words_and_uppercase_home(self):
        path = self.write(".claude/agents/a.md", "mydotfiles2 and /home/Me and /home/ and ~/x\n")
        self.assertEqual(self.edit(path), "")

    def test_both_warnings_are_emitted_rationale_first(self):
        path = self.write(".claude/skills/s/a.md", "/Users/me\nwe measured\n")
        self.assertEqual(self.edit(path),
                         "dead-prose-gate: possible banned rationale in a.md — the rule ships every dispatch; keep "
                         "the RULE, cut the defense:\n  2:we measured\n"
                         "dead-prose-gate: hardcoded path or repo name in a.md — agents, skills and commands must "
                         "be portable across WSL/Ubuntu/macOS/Arch:\n  1:/Users/me\n")

    def test_skip_variable_does_not_disable_warning(self):
        path = self.write(".claude/agents/a.md", "/Users/me\n")
        payload = {"tool_input": {"file_path": path}}
        environment = {"PATH": os.environ["PATH"], "HOME": str(self.root / "home"), "CLAUDE_SKIP_HOOKS": "1"}
        finished = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload), capture_output=True,
                                  text=True, env=environment)
        self.assertIn("hardcoded path", finished.stderr)


if __name__ == "__main__":
    unittest.main()
