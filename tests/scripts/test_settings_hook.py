"""Tests for tools/settings_hook.py: one hook entry is added or removed and every other byte stays."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from toolkit_paths import TOOLS_DIR

SCRIPT = pathlib.Path(os.environ.get("SETTINGS_HOOK_SCRIPT") or TOOLS_DIR / "settings_hook.py")

SETTINGS = {
    "model": "opus",
    "note": "café — kept as is",
    "hooks": {
        "PreToolUse": [
            {"matcher": "Bash", "hooks": [
                {"type": "command", "command": "sh a.sh"},
                {"type": "command", "command": "sh b.sh", "if": "Bash(*rg*)", "timeout": 5},
            ]},
        ],
        "Stop": [{"hooks": [{"type": "command", "command": "sh stop.sh", "async": True}]}],
        "PostToolUse": [
            {"matcher": "Agent", "hooks": [{"type": "command", "command": "sh first.sh"}]},
            {"matcher": "Agent", "hooks": [{"type": "command", "command": "sh second.sh"}]},
        ],
        "SubagentStop": [{"matcher": "", "hooks": [{"type": "command", "command": "sh sub.sh"}]}],
    },
    "permissions": {"allow": ["Read"]},
}


def render(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


class SettingsHookTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        # The script prints the resolved path; on macOS the temp folder is a symlink.
        self.settings = pathlib.Path(directory.name).resolve() / "settings.json"
        self.settings.write_text(render(SETTINGS), encoding="utf-8")

    def run_script(self, verb, event="PreToolUse", matcher="Bash", command="sh new.sh", *extra):
        matcher_arguments = [] if matcher is None else ["--matcher", matcher]
        return subprocess.run(
            [sys.executable, str(SCRIPT), verb, str(self.settings), "--event", event, *matcher_arguments,
             "--command", command, *extra],
            capture_output=True, text=True)

    def read_hooks(self):
        return json.loads(self.settings.read_text(encoding="utf-8"))["hooks"]

    def test_add_twice_writes_once(self):
        first = self.run_script("add")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("added", first.stdout)
        written = self.settings.read_bytes()
        os.utime(self.settings, (1, 1))
        second = self.run_script("add")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("already present", second.stdout)
        self.assertEqual(self.settings.read_bytes(), written)
        self.assertEqual(self.settings.stat().st_mtime, 1, "the second add must not write")

    def test_add_then_remove_restores_original_bytes(self):
        original = self.settings.read_bytes()
        for event, matcher in (("PreToolUse", "Bash"), ("PreToolUse", "Edit"), ("Notification", "idle")):
            with self.subTest(event=event, matcher=matcher):
                added = self.run_script("add", event, matcher, "sh new.sh", "--if", "Bash(*git*)", "--timeout", "7",
                                        "--async")
                self.assertEqual(added.returncode, 0, added.stderr)
                self.assertNotEqual(self.settings.read_bytes(), original)
                removed = self.run_script("remove", event, matcher, "sh new.sh", "--if", "Bash(*git*)")
                self.assertEqual(removed.returncode, 0, removed.stderr)
                self.assertIn("removed", removed.stdout)
                self.assertEqual(self.settings.read_bytes(), original)

    def test_add_appends_entry_with_optional_keys_and_leaves_the_rest(self):
        result = self.run_script("add", "PreToolUse", "Bash", "sh new.sh", "--if", "Bash(*x*)", "--timeout", "9",
                                 "--async")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(self.settings.read_text(encoding="utf-8"))
        expected = json.loads(json.dumps(SETTINGS))
        expected["hooks"]["PreToolUse"][0]["hooks"].append(
            {"type": "command", "command": "sh new.sh", "if": "Bash(*x*)", "timeout": 9, "async": True})
        self.assertEqual(data, expected)
        self.assertEqual(list(data), list(SETTINGS), "top-level key order")
        self.assertEqual(list(data["hooks"]), list(SETTINGS["hooks"]), "event order")

    def test_missing_event_and_missing_group_are_created_at_the_end(self):
        for event, matcher, command in (("Stop", "Other", "sh other.sh"), ("SessionStart", "", "sh start.sh")):
            result = self.run_script("add", event, matcher, command)
            self.assertEqual(result.returncode, 0, result.stderr)
        hooks = self.read_hooks()
        self.assertEqual(hooks["Stop"][-1], {"matcher": "Other", "hooks": [{"type": "command",
                                                                             "command": "sh other.sh"}]})
        self.assertEqual(list(hooks)[-1], "SessionStart")
        self.assertEqual(hooks["SessionStart"],
                         [{"matcher": "", "hooks": [{"type": "command", "command": "sh start.sh"}]}])

    def test_remove_drops_empty_group_then_empty_event(self):
        result = self.run_script("remove", "Stop", None, "sh stop.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        hooks = self.read_hooks()
        self.assertNotIn("Stop", hooks)
        self.assertIn("PreToolUse", hooks)

    def test_matcherless_group_is_joined_and_new_one_has_no_matcher_key(self):
        result = self.run_script("add", "Stop", None, "sh extra.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        stop = self.read_hooks()["Stop"]
        self.assertEqual(len(stop), 1)
        self.assertNotIn("matcher", stop[0])
        self.assertEqual(len(stop[0]["hooks"]), 2)
        result = self.run_script("add", "Notification", None, "sh n.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("matcher", self.read_hooks()["Notification"][0])

    def test_explicit_empty_matcher_does_not_match_matcherless_group(self):
        result = self.run_script("remove", "Stop", "", "sh stop.sh")
        self.assertIn("absent", result.stdout)
        self.assertIn("Stop", self.read_hooks())

    def test_entry_in_a_later_group_with_the_same_matcher_is_found(self):
        added = self.run_script("add", "PostToolUse", "Agent", "sh second.sh")
        self.assertIn("already present", added.stdout)
        removed = self.run_script("remove", "PostToolUse", "Agent", "sh second.sh")
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertIn("removed", removed.stdout)
        groups = self.read_hooks()["PostToolUse"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["hooks"][0]["command"], "sh first.sh")

    def test_same_command_with_different_if_is_a_separate_entry(self):
        self.run_script("add", "PreToolUse", "Bash", "sh d.sh", "--if", "Bash(*git*)")
        added = self.run_script("add", "PreToolUse", "Bash", "sh d.sh", "--if", "Bash(*gh*)")
        self.assertIn("added", added.stdout)
        removed = self.run_script("remove", "PreToolUse", "Bash", "sh d.sh", "--if", "Bash(*git*)")
        self.assertIn("removed", removed.stdout)
        remaining = [entry.get("if") for entry in self.read_hooks()["PreToolUse"][0]["hooks"]
                     if entry["command"] == "sh d.sh"]
        self.assertEqual(remaining, ["Bash(*gh*)"])

    def test_remove_drops_the_emptied_group_not_an_equal_earlier_one(self):
        empty_a = {"matcher": "A", "hooks": []}
        data = {"hooks": {"Stop": [empty_a, {"matcher": "B", "hooks": []},
                                   {"matcher": "A", "hooks": [{"type": "command", "command": "x"}]}]}}
        self.settings.write_text(render(data), encoding="utf-8")
        result = self.run_script("remove", "Stop", "A", "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read_hooks()["Stop"], [empty_a, {"matcher": "B", "hooks": []}])

    def test_remove_prunes_every_same_matcher_group_holding_the_command(self):
        entry = {"type": "command", "command": "sh dup.sh"}
        data = {"hooks": {"PostToolUse": [{"matcher": "Agent", "hooks": [dict(entry)]},
                                          {"matcher": "Agent", "hooks": [dict(entry)]}]}}
        self.settings.write_text(render(data), encoding="utf-8")
        result = self.run_script("remove", "PostToolUse", "Agent", "sh dup.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("hooks", json.loads(self.settings.read_text(encoding="utf-8")))

    def test_explicit_empty_matcher_matches_a_group_with_empty_matcher(self):
        result = self.run_script("add", "SubagentStop", "", "sh sub.sh")
        self.assertIn("already present", result.stdout)

    def test_entry_without_if_and_entry_with_if_are_different_identities(self):
        removed = self.run_script("remove", "PreToolUse", "Bash", "sh b.sh")
        self.assertIn("absent", removed.stdout)
        self.assertIn("sh b.sh", self.settings.read_text(encoding="utf-8"))
        added = self.run_script("add", "PreToolUse", "Bash", "sh b.sh")
        self.assertIn("added", added.stdout)
        commands = [(entry["command"], entry.get("if")) for entry in self.read_hooks()["PreToolUse"][0]["hooks"]]
        self.assertEqual(commands.count(("sh b.sh", None)), 1)
        self.assertEqual(commands.count(("sh b.sh", "Bash(*rg*)")), 1)

    def test_result_line_names_the_if_and_no_matcher(self):
        absent = self.run_script("remove", "PreToolUse", "Bash", "sh b.sh")
        self.assertIn("absent", absent.stdout)
        guarded = self.run_script("remove", "PreToolUse", "Bash", "sh b.sh", "--if", "Bash(*rg*)")
        self.assertIn("if Bash(*rg*)", guarded.stdout)
        matcherless = self.run_script("remove", "Stop", None, "sh stop.sh")
        self.assertIn("no matcher", matcherless.stdout)
        self.assertNotIn("None", matcherless.stdout)

    def test_remove_on_a_file_without_hooks_is_absent_and_unchanged(self):
        text = render({"a": 1})
        self.settings.write_text(text, encoding="utf-8")
        result = self.run_script("remove")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("absent", result.stdout)
        self.assertEqual(self.settings.read_text(encoding="utf-8"), text)

    def test_missing_settings_file_exits_1_and_is_not_created(self):
        self.settings.unlink()
        for verb in ("add", "remove"):
            result = self.run_script(verb)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn(str(self.settings), result.stderr)
            self.assertFalse(self.settings.exists())

    def test_file_that_is_not_utf8_exits_1_naming_the_file_without_a_traceback(self):
        raw = b"\xff\xfe{}"
        self.settings.write_bytes(raw)
        for verb in ("add", "remove"):
            result = self.run_script(verb)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn(str(self.settings), result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(self.settings.read_bytes(), raw)

    def test_usage_error_exits_2_and_leaves_the_file_unchanged(self):
        before = self.settings.read_bytes()
        missing_event = subprocess.run(
            [sys.executable, str(SCRIPT), "add", str(self.settings), "--command", "sh n.sh"],
            capture_output=True, text=True)
        bad_verb = subprocess.run(
            [sys.executable, str(SCRIPT), "toggle", str(self.settings), "--event", "Stop", "--command", "sh n.sh"],
            capture_output=True, text=True)
        self.assertEqual(missing_event.returncode, 2, missing_event.stderr)
        self.assertEqual(bad_verb.returncode, 2, bad_verb.stderr)
        self.assertEqual(self.settings.read_bytes(), before)

    def test_remove_keeps_an_empty_event_list_it_did_not_empty(self):
        data = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}], "PreToolUse": []}}
        self.settings.write_text(render(data), encoding="utf-8")
        result = self.run_script("remove", "Stop", None, "x")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read_hooks(), {"PreToolUse": []})

    def test_add_then_remove_on_a_file_without_hooks_restores_it(self):
        text = render({"a": 1})
        self.settings.write_text(text, encoding="utf-8")
        added = self.run_script("add")
        self.assertEqual(added.returncode, 0, added.stderr)
        removed = self.run_script("remove")
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertEqual(self.settings.read_text(encoding="utf-8"), text)

    def test_settings_shape_it_cannot_edit_exits_1_naming_the_file(self):
        cases = {"top level a list": [],
                 "hooks a list": {"hooks": []},
                 "event not a list": {"hooks": {"PreToolUse": {}}},
                 "group without hooks list": {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": {}}]}}}
        for name, data in cases.items():
            with self.subTest(name):
                text = render(data)
                self.settings.write_text(text, encoding="utf-8")
                for verb in ("add", "remove"):
                    result = self.run_script(verb)
                    self.assertEqual(result.returncode, 1, result.stdout)
                    self.assertIn(str(self.settings), result.stderr)
                    self.assertEqual(self.settings.read_text(encoding="utf-8"), text)

    def test_symlinked_settings_file_is_edited_in_place(self):
        link = self.settings.parent / "link.json"
        link.symlink_to(self.settings)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "add", str(link), "--event", "Notification", "--command", "sh n.sh"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(link.is_symlink())
        self.assertIn("Notification", self.read_hooks())

    def test_remove_absent_entry_writes_nothing(self):
        os.utime(self.settings, (1, 1))
        before = self.settings.read_bytes()
        for event, matcher in (("PreToolUse", "Bash"), ("PreToolUse", "Nope"), ("Nope", "Bash")):
            with self.subTest(event=event, matcher=matcher):
                result = self.run_script("remove", event, matcher, "sh missing.sh")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("absent", result.stdout)
        self.assertEqual(self.settings.read_bytes(), before)
        self.assertEqual(self.settings.stat().st_mtime, 1)

    def test_file_that_does_not_round_trip_is_refused_unchanged(self):
        cases = {"four-space indent": json.dumps(SETTINGS, indent=4) + "\n",
                 "no trailing newline": json.dumps(SETTINGS, indent=2),
                 "escaped non-ASCII": json.dumps(SETTINGS, indent=2) + "\n",
                 "not JSON": "{oops\n"}
        for name, text in cases.items():
            with self.subTest(name):
                self.settings.write_text(text, encoding="utf-8")
                for verb in ("add", "remove"):
                    result = self.run_script(verb)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(str(self.settings), result.stderr)
                    self.assertEqual(self.settings.read_text(encoding="utf-8"), text)


if __name__ == "__main__":
    unittest.main()
