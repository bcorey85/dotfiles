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

LOCK = "home/.local/state/claude-calibration/lock.json"
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


def run_hook(lock_text=None, old_lock_text=None, state_home=None):
    """Lock text goes to the state-dir lock (under state_home when given, else $HOME/.local/state);
    old_lock_text goes to the pre-move lock under ~/.claude."""
    with tempfile.TemporaryDirectory() as scratch:
        home = pathlib.Path(scratch) / "home"
        (home / ".claude").mkdir(parents=True)
        environment = {key: value for key, value in os.environ.items() if key != "XDG_STATE_HOME"}
        environment.update(HOME=str(home), TMPDIR=scratch)
        state_root = home / ".local" / "state"
        if state_home is not None:
            state_root = pathlib.Path(scratch) / state_home
            environment["XDG_STATE_HOME"] = str(state_root)
        lock_path = state_root / "claude-calibration" / "lock.json"
        old_lock_path = home / ".claude" / "calibration-lock.json"
        if lock_text is not None:
            lock_path.parent.mkdir(parents=True)
            lock_path.write_text(lock_text)
        if old_lock_text is not None:
            old_lock_path.write_text(old_lock_text)
        finished = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, env=environment)
        text = finished.stdout.decode("utf-8").replace(str(lock_path), "<LOCK>").replace(str(old_lock_path), "<OLD-LOCK>")
        return finished, text


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
            (pathlib.Path(scratch) / ".local" / "state" / "claude-calibration" / "lock.json").mkdir(parents=True)
            (pathlib.Path(scratch) / ".claude" / "calibration-lock.json").mkdir(parents=True)
            environment = {key: value for key, value in os.environ.items() if key != "XDG_STATE_HOME"}
            environment["HOME"] = scratch
            finished = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, env=environment)
            self.assertEqual((finished.returncode, finished.stdout), (0, b""))

    def test_lock_under_xdg_state_home_is_reported(self):
        finished, text = run_hook(FULL_LOCK, state_home="custom-state")
        self.assertEqual(finished.returncode, 0)
        self.assertIn("CALIBRATION SEED", text)
        self.assertIn('  rm "<LOCK>"\n', text)

    def test_xdg_state_home_lock_is_the_only_one_read_when_set(self):
        # With XDG_STATE_HOME set, the default $HOME/.local/state lock is not consulted.
        with tempfile.TemporaryDirectory() as scratch:
            home = pathlib.Path(scratch) / "home"
            default_lock = home / ".local" / "state" / "claude-calibration" / "lock.json"
            default_lock.parent.mkdir(parents=True)
            default_lock.write_text(FULL_LOCK)
            environment = dict(os.environ, HOME=str(home), XDG_STATE_HOME=str(pathlib.Path(scratch) / "elsewhere"))
            finished = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, env=environment)
            self.assertEqual((finished.returncode, finished.stdout), (0, b""))

    def test_lock_left_at_the_old_path_is_still_reported(self):
        finished, text = run_hook(old_lock_text=FULL_LOCK)
        self.assertEqual(finished.returncode, 0)
        self.assertIn("CALIBRATION SEED", text)
        self.assertIn('  rm "<OLD-LOCK>"\n', text)

    def test_new_path_lock_wins_over_the_old_one(self):
        _, text = run_hook(json.dumps({"file": "new.ts"}), old_lock_text=json.dumps({"file": "old.ts"}))
        self.assertIn("new.ts", text)
        self.assertNotIn("old.ts", text)


if __name__ == "__main__":
    unittest.main()
