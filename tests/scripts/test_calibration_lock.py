"""Checks for lib/calibration_lock.py, the owner of the calibration and mutation lock format.

Set CALIBRATION_LOCK_MODULE to run against another copy of the module."""
import importlib.util
import os
import pathlib
import sys
import unittest
import unittest.mock

import toolkit_paths

MODULE_PATH = pathlib.Path(os.environ.get("CALIBRATION_LOCK_MODULE") or toolkit_paths.LIB_DIR / "calibration_lock.py")
sys.path.insert(0, str(MODULE_PATH.parent))
import hook_input  # noqa: E402,F401  (the module under test imports it; the parent is on sys.path first)

SPEC = importlib.util.spec_from_file_location("calibration_lock_under_test", MODULE_PATH)
calibration_lock = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(calibration_lock)


class PathTest(unittest.TestCase):
    def test_lock_path_is_tidied_by_the_state_root_owner(self):
        with unittest.mock.patch.dict(os.environ, {"HOME": "/h", "XDG_STATE_HOME": "/a//b"}):
            self.assertEqual(calibration_lock.calibration_lock_path(), "/a/b/claude-calibration/lock.json")

    def test_lock_path_uses_xdg_state_home_when_set(self):
        with unittest.mock.patch.dict(os.environ, {"HOME": "/h", "XDG_STATE_HOME": "/s"}):
            self.assertEqual(calibration_lock.calibration_lock_path(), "/s/claude-calibration/lock.json")

    def test_lock_path_ignores_a_relative_xdg_state_home(self):
        with unittest.mock.patch.dict(os.environ, {"HOME": "/h", "XDG_STATE_HOME": "rel"}):
            self.assertEqual(calibration_lock.calibration_lock_path(), "/h/.local/state/claude-calibration/lock.json")

    def test_lock_path_falls_back_to_the_home_state_folder(self):
        with unittest.mock.patch.dict(os.environ, {"HOME": "/h"}):
            os.environ.pop("XDG_STATE_HOME", None)
            self.assertEqual(calibration_lock.calibration_lock_path(), "/h/.local/state/claude-calibration/lock.json")

    def test_legacy_lock_path_is_under_home(self):
        with unittest.mock.patch.dict(os.environ, {"HOME": "/h"}):
            self.assertEqual(calibration_lock.legacy_lock_path(), "/h/.claude/calibration-lock.json")


class StampTest(unittest.TestCase):
    def test_offset_form_does_not_parse(self):
        self.assertIsNone(calibration_lock.parse_stamp("2026-10-01T10:00:00+00:00"))


class LockViewTest(unittest.TestCase):
    def test_relative_file_is_joined_to_the_worktree_and_absolute_is_left_alone(self):
        relative = calibration_lock.read_lock_view('{"file": "src/a.ts", "worktree": "/work"}')
        absolute = calibration_lock.read_lock_view('{"file": "/other/a.ts", "worktree": "/work"}')
        self.assertEqual(relative.file, "/work/src/a.ts")
        self.assertEqual(absolute.file, "/other/a.ts")


class LockFieldTest(unittest.TestCase):
    def test_field_reads_follow_the_jq_default_and_fallback_rules(self):
        cases = [
            ("unreadable lock gives the fallback", None, "?", "FB"),
            ("present value", '{"file": "a"}', "?", "a"),
            ("missing key takes the default", "{}", "?", "?"),
            ("null takes the default", '{"file": null}', "?", "?"),
            ("false takes the default", '{"file": false}', "?", "?"),
            ("two documents give two lines", '{"file": "a"}\n{"file": "b"}', "?", "a\nb"),
            ("a non-object document appends the fallback", '{"file": "a"} 5', "?", "a\nFB"),
            ("a broken document appends the fallback", '{"file": "a"} {', "?", "a\nFB"),
        ]
        for name, text, default, expected in cases:
            with self.subTest(name):
                self.assertEqual(calibration_lock.lock_field(text, "file", default, "FB"), expected)


class LockIsLiveTest(unittest.TestCase):
    NOW = calibration_lock.parse_stamp("2026-10-01T10:00:00Z")

    def test_liveness_follows_age_owner_and_writer(self):
        young = "2026-10-01T09:50:00Z"
        old = "2026-10-01T07:00:00Z"
        at_timeout = calibration_lock.format_stamp(self.NOW - calibration_lock.MUTATION_RUN_TIMEOUT_SECONDS)
        past_timeout = calibration_lock.format_stamp(self.NOW - calibration_lock.MUTATION_RUN_TIMEOUT_SECONDS - 1)
        mine = str(os.getpid())
        cases = [
            ("young with no owner", (young, ""), {}, True),
            ("young with a live owner", (young, mine), {}, True),
            ("young with a dead owner", (young, "999999999"), {}, False),
            ("past the timeout", (old, ""), {}, False),
            ("exactly at the timeout", (at_timeout, ""), {}, True),
            ("a second past the timeout", (past_timeout, ""), {}, False),
            ("unparseable stamp", ("not a time", ""), {}, False),
            ("calibrate lock of the caller's session", (young, mine), {"writer": "calibrate", "session_pid": mine},
             False),
            ("calibrate lock with no session pid", (young, mine), {"writer": "calibrate", "session_pid": ""}, True),
            ("calibrate lock with no owner and no session pid", (young, ""),
             {"writer": "calibrate", "session_pid": ""}, True),
            ("calibrate lock of another session", (young, mine), {"writer": "calibrate", "session_pid": "1"}, True),
            ("mutation-tester lock of the caller's session", (young, mine),
             {"writer": "mutation-tester", "session_pid": mine}, True),
        ]
        for name, positional, keywords, expected in cases:
            with self.subTest(name):
                self.assertEqual(calibration_lock.lock_is_live(*positional, self.NOW, **keywords), expected)


class RecoveryCommandsTest(unittest.TestCase):
    def test_paths_with_shell_characters_are_quoted(self):
        view = calibration_lock.read_lock_view('{"file": "/w/a $(x).ts", "backup_path": "/b/a\\"q", "worktree": "/w"}')
        copy_command, remove_command = calibration_lock.recovery_commands(view, "/l/it's")
        self.assertEqual(copy_command, "cp '/b/a\"q' '/w/a $(x).ts'")
        self.assertEqual(remove_command, 'rm "/l/it\'s"')


if __name__ == "__main__":
    unittest.main()
