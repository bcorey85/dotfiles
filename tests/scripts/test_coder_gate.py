"""Tests for coder-gate.py: the variables a gate runs its commands with."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
REAL_CLAUDE = pathlib.Path(os.environ.get("CODE_STEP_REAL_CLAUDE") or HERE.parent.parent / "claude" / ".claude")
GATE_SCRIPT = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or REAL_CLAUDE / "scripts") / "coder-gate.py"
GIT_IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
                "GIT_COMMITTER_EMAIL": "t@example.com"}


class CoderGateEnvironmentTests(unittest.TestCase):
    def setUp(self):
        tempDirectory = tempfile.TemporaryDirectory()
        self.addCleanup(tempDirectory.cleanup)
        self.repo = pathlib.Path(tempDirectory.name) / "repo"
        self.repo.mkdir()
        self.home = pathlib.Path(tempDirectory.name) / "home"
        self.home.mkdir()
        self.env = {**os.environ, **GIT_IDENTITY, "HOME": str(self.home)}
        self.env.pop("GATE_PROBE", None)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True, env=self.env)

    def gate_set(self, *arguments):
        return subprocess.run([sys.executable, "-B", str(GATE_SCRIPT), "set", *arguments], cwd=self.repo, env=self.env,
                              capture_output=True, text=True)

    def gate_hook(self):
        event = {"agent_type": "coder", "agent_id": "a1", "cwd": str(self.repo),
                 "tool_input": {"message": "BEHAVIOR: done"}}
        return subprocess.run([sys.executable, "-B", str(GATE_SCRIPT), "hook"], cwd=self.repo, env=self.env,
                              input=json.dumps(event), capture_output=True, text=True)

    def stored_gate(self):
        return json.loads((self.repo / ".git/coder-gate.json").read_text())

    def test_set_stores_each_variable_with_its_value_unquoted(self):
        done = self.gate_set("--env", "A=1", "--env", 'B="two words"', "--env", "C='x y'", "--env", "D=",
                             "python3 -m pytest tests/test_one.py")

        self.assertEqual(0, done.returncode, done.stderr)
        self.assertEqual({"A": "1", "B": "two words", "C": "x y", "D": ""}, self.stored_gate()["env"])
        self.assertEqual(["python3 -m pytest tests/test_one.py"], self.stored_gate()["commands"])

    def test_set_with_no_variable_stores_an_empty_environment(self):
        self.gate_set("python3 -m pytest tests/test_one.py")

        self.assertEqual({}, self.stored_gate()["env"])

    def test_set_refuses_a_word_that_is_not_a_variable_assignment(self):
        for word in ("not-an-assignment", "A=1 B=2", "=1", "A='unclosed"):
            with self.subTest(word=word):
                done = self.gate_set("--env", word, "python3 -m pytest tests/test_one.py")

                self.assertNotEqual(0, done.returncode)
                self.assertIn("--env needs NAME=value", done.stderr)

    def test_set_refuses_a_trailing_env_flag_with_no_value(self):
        for arguments in (("python3 -m pytest tests/test_one.py", "--env"), ("--env", "A=1", "--env"), ("--env",)):
            with self.subTest(arguments=arguments):
                done = self.gate_set(*arguments)

                self.assertNotEqual(0, done.returncode)
                self.assertIn("--env needs NAME=value", done.stderr)
                self.assertFalse((self.repo / ".git/coder-gate.json").exists())

    def test_the_hook_runs_each_command_with_the_stored_variables(self):
        probe = 'test "$GATE_PROBE" = "two words"'
        self.gate_set("--env", 'GATE_PROBE="two words"', probe, f"cd . && {probe}")

        done = self.gate_hook()

        self.assertEqual(0, done.returncode, done.stderr)
        self.assertEqual("pass", self.stored_gate()["coders"]["a1"]["result"])

    def test_the_hook_denies_a_command_that_needs_a_variable_the_gate_was_not_given(self):
        self.gate_set('test "$GATE_PROBE" = 1')

        done = self.gate_hook()

        self.assertEqual("deny", self.stored_gate()["coders"]["a1"]["result"])
        self.assertIn("deny", done.stdout)

    def test_a_gate_stored_before_variables_existed_still_runs(self):
        self.gate_set("true")
        gate = self.stored_gate()
        del gate["env"]
        (self.repo / ".git/coder-gate.json").write_text(json.dumps(gate))

        self.gate_hook()

        self.assertEqual("pass", self.stored_gate()["coders"]["a1"]["result"])


if __name__ == "__main__":
    unittest.main()
