"""Checks for calibration-guard.py, the SessionStart hook that reports an unrestored calibration or mutation seed.

Set HOOK_SCRIPTS_DIR to run against another directory of scripts."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or pathlib.Path.home() / ".claude" / "scripts") / "calibration-guard.py"

LOCK = "home/.claude/calibration-lock.json"
FULL_LOCK = json.dumps({"file": "src/a.ts", "backup_path": "/tmp/a.ts.bak", "class": "off-by-one",
                        "ts": "2026-10-01T10:00:00Z", "kind": "calibrate"})

PARITY_CASES = [
    {"name": "no lock", "stdin": ""},
    {"name": "calibrate lock", "stdin": "", "files": {LOCK: FULL_LOCK}},
    {"name": "mutation lock", "stdin": "",
     "files": {LOCK: json.dumps({"file": "f", "backup_path": "b", "class": "c", "ts": "t", "kind": "mutation-test"})}},
    {"name": "unknown kind", "stdin": "", "files": {LOCK: json.dumps({"file": "f", "kind": "other"})}},
    {"name": "missing fields", "stdin": "", "files": {LOCK: "{}"}},
    {"name": "null fields", "stdin": "",
     "files": {LOCK: '{"file":null,"backup_path":false,"class":null,"ts":null,"kind":null}'}},
    {"name": "numeric fields", "stdin": "", "files": {LOCK: '{"file":12,"backup_path":1.5,"class":true,"ts":0}'}},
    {"name": "object field", "stdin": "", "files": {LOCK: '{"file":{"a":[1,2]},"class":[]}'}},
    {"name": "invalid json", "stdin": "", "files": {LOCK: "not json"}},
    {"name": "empty lock file", "stdin": "", "files": {LOCK: ""}},
    {"name": "whitespace lock file", "stdin": "", "files": {LOCK: "\n\n"}},
    {"name": "array lock", "stdin": "", "files": {LOCK: "[1,2]"}},
    {"name": "null lock", "stdin": "", "files": {LOCK: "null"}},
    {"name": "string lock", "stdin": "", "files": {LOCK: '"x"'}},
    {"name": "two documents", "stdin": "", "files": {LOCK: '{"file":"a"}\n{"file":"b"}'}},
    {"name": "document then garbage", "stdin": "", "files": {LOCK: '{"file":"a"} nope'}},
    {"name": "unicode and quotes", "stdin": "",
     "files": {LOCK: json.dumps({"file": "dir/é \"q\".ts", "class": "it's", "backup_path": "a b"})}},
    {"name": "trailing newline in value", "stdin": "", "files": {LOCK: '{"file":"a\\n\\n","kind":"mutation-test\\n"}'}},
    {"name": "skip hooks is not honored", "stdin": "", "env": {"CLAUDE_SKIP_HOOKS": "1"}, "files": {LOCK: FULL_LOCK}},
]
TYPICAL = {"name": "typical", "stdin": "", "files": {LOCK: FULL_LOCK}}


def run_hook(lock_text=None):
    with tempfile.TemporaryDirectory() as scratch:
        home = pathlib.Path(scratch) / "home"
        (home / ".claude").mkdir(parents=True)
        if lock_text is not None:
            (home / ".claude" / "calibration-lock.json").write_text(lock_text)
        environment = dict(os.environ, HOME=str(home), TMPDIR=scratch)
        finished = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, env=environment)
        lock_path = str(home / ".claude" / "calibration-lock.json")
        return finished, finished.stdout.decode("utf-8").replace(lock_path, "<LOCK>")


class CalibrationGuardTest(unittest.TestCase):
    def test_no_lock_prints_nothing(self):
        finished, text = run_hook()
        self.assertEqual((finished.returncode, text, finished.stderr), (0, "", b""))

    def test_calibrate_lock_message_is_exact(self):
        finished, text = run_hook(FULL_LOCK)
        self.assertEqual(finished.returncode, 0)
        self.assertEqual(text, (
            "⚠️  UNRESTORED CALIBRATION SEED — a previous /calibrate run did not finish.\n"
            "\n"
            "A deliberate 'off-by-one' mutation was applied at 2026-10-01T10:00:00Z and may still be in:\n"
            "  src/a.ts\n"
            "\n"
            "Restore it from the backup before doing ANY other work in that repo:\n"
            "  cp \"/tmp/a.ts.bak\" \"src/a.ts\"\n"
            "\n"
            "Then verify the file is back to what you expect and remove the lock:\n"
            "  rm \"<LOCK>\"\n"
            "\n"
            "Do not commit until this is resolved. Do not run /calibrate or dispatch\n"
            "mutation-tester until this lock is gone — both refuse to seed on top of an\n"
            "unrestored seed.\n"))

    def test_mutation_kind_changes_the_headline(self):
        _, text = run_hook(json.dumps({"kind": "mutation-test"}))
        self.assertTrue(text.startswith("⚠️  UNRESTORED MUTATION SEED — a previous mutation-tester run did not finish.\n"))

    def test_unknown_or_missing_kind_is_a_calibration_seed(self):
        for lock in ('{"kind":"other"}', "{}", '{"kind":null}'):
            _, text = run_hook(lock)
            self.assertIn("CALIBRATION SEED", text)

    def test_missing_fields_print_question_marks(self):
        _, text = run_hook("{}")
        self.assertIn("A deliberate '?' mutation was applied at ? and may still be in:\n  ?\n", text)
        self.assertIn('  cp "?" "?"\n', text)

    def test_invalid_json_prints_question_marks_and_calibrate(self):
        finished, text = run_hook("not json")
        self.assertEqual(finished.returncode, 0)
        self.assertIn("CALIBRATION SEED", text)
        self.assertIn('  cp "?" "?"\n', text)

    def test_empty_lock_file_gives_empty_fields_not_question_marks(self):
        _, text = run_hook("")
        self.assertIn("A deliberate '' mutation was applied at  and may still be in:\n  \n", text)

    def test_non_object_lock_prints_question_marks(self):
        for lock in ("[1]", '"x"'):
            _, text = run_hook(lock)
            self.assertIn('  cp "?" "?"\n', text)

    def test_null_lock_uses_defaults(self):
        _, text = run_hook("null")
        self.assertIn('  cp "?" "?"\n', text)
        self.assertIn("CALIBRATION SEED", text)

    def test_non_string_values_print_like_jq_raw_output(self):
        _, text = run_hook('{"file":12,"backup_path":1.5,"class":true,"ts":0}')
        self.assertIn("applied at 0 and may still be in:\n  12\n", text)
        self.assertIn("'true' mutation", text)
        self.assertIn('cp "1.5"', text)

    def test_object_value_prints_pretty_json(self):
        _, text = run_hook('{"file":{"a":[1]}}')
        self.assertIn('  {\n  "a": [\n    1\n  ]\n}\n', text)

    def test_false_value_uses_default(self):
        _, text = run_hook('{"file":false}')
        self.assertIn("may still be in:\n  ?\n", text)

    def test_two_documents_give_two_lines(self):
        _, text = run_hook('{"file":"a"}\n{"file":"b"}')
        self.assertIn("may still be in:\n  a\nb\n", text)

    def test_document_then_garbage_appends_fallback(self):
        _, text = run_hook('{"file":"a"} nope')
        self.assertIn("may still be in:\n  a\n?\n", text)

    def test_trailing_newlines_in_values_are_stripped(self):
        _, text = run_hook('{"file":"a\\n\\n","kind":"mutation-test\\n"}')
        self.assertIn("may still be in:\n  a\n\n", text)
        self.assertIn("MUTATION SEED", text)

    def test_directory_at_lock_path_is_not_a_lock(self):
        with tempfile.TemporaryDirectory() as scratch:
            (pathlib.Path(scratch) / ".claude" / "calibration-lock.json").mkdir(parents=True)
            finished = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True,
                                      env=dict(os.environ, HOME=scratch))
            self.assertEqual((finished.returncode, finished.stdout), (0, b""))


if __name__ == "__main__":
    unittest.main()
