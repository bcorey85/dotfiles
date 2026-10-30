"""Checks for emit_orchestration.py, the SessionStart hook that injects ~/.claude/orchestration.md.

Set HOOK_SCRIPTS_DIR to run against another directory of scripts."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or toolkit_paths.GATES_DIR) / "emit_orchestration.py"

WARNING = ("WARNING: ~/.claude/orchestration.md is missing or unreadable. Delegation rules are NOT loaded this "
           "session. Tell the user before coding or dispatching any work.")


FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


def run_hook(content=None, unreadable=False, stdin=b""):
    with tempfile.TemporaryDirectory() as scratch:
        home = pathlib.Path(scratch) / "home"
        (home / ".claude").mkdir(parents=True)
        target = home / ".claude" / "orchestration.md"
        if content is not None:
            target.write_bytes(content)
            if unreadable:
                target.chmod(0)
        environment = dict(os.environ, HOME=str(home), TMPDIR=scratch)
        finished = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, env=environment,
                                  input=stdin)
        if content is not None:
            target.chmod(0o600)
        return finished


class EmitOrchestrationTest(unittest.TestCase):
    def test_file_content_becomes_additional_context(self):
        finished = run_hook(b"# Rules\n\nDelegate.\n")
        self.assertEqual((finished.returncode, finished.stderr), (0, b""))
        output = json.loads(finished.stdout)
        self.assertEqual(output, {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                         "additionalContext": "# Rules\n\nDelegate.\n"}})

    def test_main_session_input_emits_rules(self):
        finished = run_hook(b"# Rules\n", stdin=(FIXTURES / "hook_event_session_start_main.json").read_bytes())
        self.assertEqual(finished.returncode, 0)
        self.assertEqual(json.loads(finished.stdout)["hookSpecificOutput"]["additionalContext"], "# Rules\n")

    def test_agent_seat_input_emits_nothing(self):
        finished = run_hook(b"# Rules\n", stdin=(FIXTURES / "hook_event_session_start_agent.json").read_bytes())
        self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, b"", b""))

    def test_unusable_agent_type_or_stdin_still_emits_rules(self):
        cases = {
            "empty agent_type": json.dumps({"agent_type": ""}).encode(),
            "non-string agent_type": json.dumps({"agent_type": 3}).encode(),
            "non-object json": b"[1, 2]",
            "non-json": b"not json{",
            "empty stdin": b"",
        }
        for label, stdin in cases.items():
            with self.subTest(label):
                finished = run_hook(b"# Rules\n", stdin=stdin)
                self.assertEqual(finished.returncode, 0)
                self.assertEqual(json.loads(finished.stdout)["hookSpecificOutput"]["additionalContext"],
                                 "# Rules\n")
                if label == "non-json":
                    self.assertIn("emit-orchestration: cannot parse hook input", finished.stderr.decode("utf-8"))
                    self.assertIn("; loading rules\n", finished.stderr.decode("utf-8"))
                else:
                    self.assertEqual(finished.stderr, b"")

    def test_unreadable_stdin_still_emits_rules(self):
        with tempfile.TemporaryDirectory() as scratch:
            home = pathlib.Path(scratch) / "home"
            (home / ".claude").mkdir(parents=True)
            (home / ".claude" / "orchestration.md").write_bytes(b"# Rules\n")
            environment = dict(os.environ, HOME=str(home), TMPDIR=scratch)
            write_only_fd = os.open(os.devnull, os.O_WRONLY)
            try:
                finished = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, env=environment,
                                          stdin=write_only_fd)
            finally:
                os.close(write_only_fd)
        self.assertEqual(finished.returncode, 0)
        self.assertEqual(json.loads(finished.stdout)["hookSpecificOutput"]["additionalContext"], "# Rules\n")
        self.assertIn("emit-orchestration: cannot read hook input", finished.stderr.decode("utf-8"))

    def test_missing_file_emits_compact_warning(self):
        finished = run_hook()
        self.assertEqual(finished.returncode, 0)
        self.assertEqual(finished.stdout.decode("utf-8"),
                         json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                            "additionalContext": WARNING}},
                                    separators=(",", ":"), ensure_ascii=False) + "\n")

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root reads everything")
    def test_unreadable_file_emits_warning(self):
        finished = run_hook(b"secret", unreadable=True)
        self.assertIn("missing or unreadable", finished.stdout.decode("utf-8"))
        self.assertEqual(finished.returncode, 0)

    def test_empty_file_gives_empty_context(self):
        finished = run_hook(b"")
        self.assertEqual(json.loads(finished.stdout)["hookSpecificOutput"]["additionalContext"], "")

    def test_invalid_utf8_is_replaced_not_fatal(self):
        finished = run_hook(b"a\xffb")
        self.assertEqual(finished.returncode, 0)
        self.assertEqual(json.loads(finished.stdout)["hookSpecificOutput"]["additionalContext"], "a\ufffdb")


if __name__ == "__main__":
    unittest.main()
