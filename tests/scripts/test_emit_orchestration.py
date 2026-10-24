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

ORCHESTRATION = "home/.claude/orchestration.md"
WARNING = ("WARNING: ~/.claude/orchestration.md is missing or unreadable. Delegation rules are NOT loaded this "
           "session. Tell the user before coding or dispatching any work.")

PARITY_CASES = [
    {"name": "missing file", "stdin": ""},
    {"name": "plain file", "stdin": "", "files": {ORCHESTRATION: "# Rules\n\nDelegate.\n"}},
    {"name": "empty file", "stdin": "", "files": {ORCHESTRATION: ""}},
    {"name": "no trailing newline", "stdin": "", "files": {ORCHESTRATION: "abc"}},
    {"name": "quotes backslash tab", "stdin": "", "files": {ORCHESTRATION: 'say "hi"\\n\ttab \\ done\n'}},
    {
        "name": "unicode",
        "stdin": "",
        "files": {ORCHESTRATION: "caf\u00e9 \u2014 \u26a0\ufe0f \U0001f600 \u65e5\u672c\n"},
    },
    {"name": "del and control chars", "stdin": "", "files": {ORCHESTRATION: "a\x7fb\x01c\x1bd\r\n"}},
    {"name": "blank lines", "stdin": "", "files": {ORCHESTRATION: "\n\n\nx\n\n\n"}},
    {"name": "directory instead of file", "stdin": "", "files": {ORCHESTRATION + "/keep": "x"}},
    {"name": "stdin ignored", "stdin": '{"hook_event_name":"SessionStart"}', "files": {ORCHESTRATION: "x\n"}},
    {"name": "skip hooks not honored", "stdin": "", "env": {"CLAUDE_SKIP_HOOKS": "1"}, "files": {ORCHESTRATION: "x\n"}},
]
TYPICAL = {
    "name": "typical",
    "stdin": "",
    "files": {ORCHESTRATION: "# Orchestration\n" + "Delegate to agents.\n" * 200},
}


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

    def test_output_is_pretty_printed_like_jq(self):
        finished = run_hook(b"x\n")
        self.assertEqual(finished.stdout.decode("utf-8"),
                         '{\n  "hookSpecificOutput": {\n    "hookEventName": "SessionStart",\n'
                         '    "additionalContext": "x\\n"\n  }\n}\n')

    def test_unicode_is_not_escaped_but_del_is(self):
        finished = run_hook("caf\u00e9 \U0001f600 a\x7fb".encode("utf-8"))
        text = finished.stdout.decode("utf-8")
        self.assertIn("caf\u00e9 \U0001f600 a\\u007fb", text)

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
