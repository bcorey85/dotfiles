"""Checks for test-edit-telemetry.py, the log-only PreToolUse hook that records edits to test files."""
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or pathlib.Path.home() / ".claude" / "scripts")
SCRIPT = SCRIPTS_DIR / "test-edit-telemetry.py"

TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestEditTelemetryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name).resolve()
        self.home = self.root / "home"
        (self.home / ".claude").mkdir(parents=True)
        self.log = self.home / ".claude" / "test-edit-telemetry.jsonl"

    def run_hook(self, payload, env=None, cwd=None, stderr=""):
        environment = {"PATH": os.environ["PATH"], "HOME": str(self.home), "TMPDIR": str(self.root)}
        environment.update(env or {})
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        finished = subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True,
                                  env=environment, cwd=cwd or str(self.root))
        self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, "", stderr))

    def edit(self, path, stderr="", **extra):
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Edit",
                   "tool_input": {"file_path": path, "new_string": "assert x == 1"}}
        payload.update(extra)
        self.run_hook(payload, stderr=stderr)

    def rows(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_invalid_input_logs_nothing(self):
        for stdin in ("not json", "", json.dumps({"tool_input": {}}), json.dumps({"tool_input": {"file_path": ""}})):
            self.run_hook(stdin)
        self.assertFalse(self.log.exists())

    def test_test_file_patterns_are_logged(self):
        paths = ["/r/a_test.go", "/r/a.test.ts", "/r/a.test.tsx", "/r/a.test.js", "/r/a.test.jsx", "/r/a.spec.ts",
                 "/r/a.spec.tsx", "/r/a.spec.js", "/r/a.spec.jsx", "/r/a_spec.rb", "/r/test_a.py", "/r/a_test.py",
                 "/r/conftest.py", "/r/tests/x.txt", "/r/testdata/x.txt", "/r/fixtures/x.txt", "/r/__tests__/x.js",
                 "/r/__mocks__/x.js"]
        for path in paths:
            self.edit(path)
        self.assertEqual([row["file"] for row in self.rows()], paths)

    def test_other_files_are_not_logged(self):
        for path in ("/r/a.py", "/r/test_a.txt", "test_a.py", "/r/latest.py", "/r/tests", "/r/contest.py",
                     "conftest.py"):
            self.edit(path)
        self.assertEqual(self.rows(), [])

    def test_row_keys_and_values(self):
        self.edit("/r/a_test.py", agent_type="coder", agent_id="abc")
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(list(row), ["ts", "tool", "agent", "file", "cwd", "snippet"])
        self.assertRegex(row["ts"], TIMESTAMP)
        self.assertEqual((row["tool"], row["agent"], row["file"], row["cwd"], row["snippet"]),
                         ("Edit", "coder", "/r/a_test.py", str(self.root), "assert x == 1"))

    def test_row_is_compact_json_one_per_line(self):
        self.edit("/r/a_test.py")
        text = self.log.read_text()
        self.assertTrue(text.endswith("}\n"))
        self.assertNotIn(", ", text.split('"snippet"')[0])
        self.assertNotIn('": ', text)

    def test_agent_defaults_to_main(self):
        self.edit("/r/a_test.py")
        self.assertEqual(self.rows()[0]["agent"], "main")

    def test_snippet_prefers_new_string_then_content_then_empty(self):
        self.run_hook({"tool_name": "Write", "tool_input": {"file_path": "/r/a_test.py", "content": "from content"}})
        self.run_hook({"tool_name": "Write",
                       "tool_input": {"file_path": "/r/a_test.py", "content": "c", "new_string": "from new"}})
        self.run_hook({"tool_name": "Write", "tool_input": {"file_path": "/r/a_test.py"}})
        self.assertEqual([row["snippet"] for row in self.rows()], ["from content", "from new", ""])

    def test_snippet_is_cut_to_200_characters(self):
        self.run_hook({"tool_name": "Write", "tool_input": {"file_path": "/r/a_test.py", "content": "é" * 300}})
        self.assertEqual(self.rows()[0]["snippet"], "é" * 200)

    def test_rows_append(self):
        self.edit("/r/a_test.py")
        self.edit("/r/b_test.py")
        self.assertEqual([row["file"] for row in self.rows()], ["/r/a_test.py", "/r/b_test.py"])

    def test_cwd_is_the_hook_process_directory(self):
        sub = self.root / "sub"
        sub.mkdir()
        payload = {"tool_name": "Edit", "tool_input": {"file_path": "/r/a_test.py"}, "cwd": "/elsewhere"}
        self.run_hook(payload, env={"PWD": str(sub)}, cwd=str(sub))
        self.assertEqual(self.rows()[0]["cwd"], str(sub))

    def test_skip_variable_disables_logging(self):
        self.run_hook({"tool_name": "Edit", "tool_input": {"file_path": "/r/a_test.py"}},
                      env={"CLAUDE_SKIP_HOOKS": "1"})
        self.assertFalse(self.log.exists())

    def test_missing_log_directory_is_ignored(self):
        self.home = self.root / "nohome"
        self.home.mkdir()
        log = self.home / ".claude" / "test-edit-telemetry.jsonl"
        shell_message = "test-edit-telemetry: cannot open %s: No such file or directory\n" % log
        self.edit("/r/a_test.py", stderr=shell_message)
        self.assertFalse((self.home / ".claude").exists())

    def test_control_characters_are_escaped_like_jq(self):
        self.run_hook({"tool_name": "Edit", "tool_input": {"file_path": "/r/a_test.py", "new_string": "a\x01\x7f\n\"b"}})
        self.assertIn('"snippet":"a\\u0001\\u007f\\n\\"b"', self.log.read_text())

    def test_non_string_snippet_logs_nothing(self):
        self.run_hook({"tool_name": "Edit", "tool_input": {"file_path": "/r/a_test.py", "new_string": 5}})
        self.assertEqual(self.rows(), [])


if __name__ == "__main__":
    unittest.main()
