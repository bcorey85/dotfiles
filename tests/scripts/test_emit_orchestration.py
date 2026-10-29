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


def run_hook(content=None, unreadable=False):
    with tempfile.TemporaryDirectory() as scratch:
        home = pathlib.Path(scratch) / "home"
        (home / ".claude").mkdir(parents=True)
        target = home / ".claude" / "orchestration.md"
        if content is not None:
            target.write_bytes(content)
            if unreadable:
                target.chmod(0)
        environment = dict(os.environ, HOME=str(home), TMPDIR=scratch)
        finished = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, env=environment)
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
