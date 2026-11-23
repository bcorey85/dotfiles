"""Checks for lib/calibration_lock.py, the owner of the calibration and mutation lock format.

Set CALIBRATION_LOCK_MODULE to run against another copy of the module."""
import importlib.util
import os
import pathlib
import sys
import tempfile
import time
import unittest

import toolkit_paths

MODULE_PATH = pathlib.Path(os.environ.get("CALIBRATION_LOCK_MODULE") or toolkit_paths.LIB_DIR / "calibration_lock.py")
sys.path.insert(0, str(MODULE_PATH.parent))
import hook_input  # noqa: E402,F401  (the module under test imports it; the parent is on sys.path first)

SPEC = importlib.util.spec_from_file_location("calibration_lock_under_test", MODULE_PATH)
calibration_lock = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(calibration_lock)


class PathTest(unittest.TestCase):
    def test_lock_path_uses_xdg_state_home_when_set(self):
        environ = {"HOME": "/home/u", "XDG_STATE_HOME": "/state"}
        self.assertEqual(calibration_lock.lock_path(environ), "/state/claude-calibration/lock.json")

    def test_lock_path_falls_back_to_home_local_state(self):
        environ = {"HOME": "/home/u"}
        self.assertEqual(calibration_lock.lock_path(environ), "/home/u/.local/state/claude-calibration/lock.json")

    def test_lock_path_keeps_the_environment_text_untidied(self):
        self.assertEqual(
            calibration_lock.lock_path({"HOME": "/h", "XDG_STATE_HOME": "/a//b"}), "/a//b/claude-calibration/lock.json"
        )
        self.assertEqual(
            calibration_lock.lock_path({"HOME": "/h", "XDG_STATE_HOME": "./s"}), "./s/claude-calibration/lock.json"
        )

    def test_find_lock_returns_the_legacy_path_only_when_the_state_lock_is_absent(self):
        with tempfile.TemporaryDirectory() as scratch:
            home = pathlib.Path(scratch)
            environ = {"HOME": str(home)}
            legacy = pathlib.Path(calibration_lock.legacy_lock_path(environ))
            legacy.parent.mkdir(parents=True)
            legacy.write_text("{}")
            self.assertEqual(calibration_lock.find_lock(environ), str(legacy))
            current = pathlib.Path(calibration_lock.lock_path(environ))
            current.parent.mkdir(parents=True)
            current.write_text("{}")
            self.assertEqual(calibration_lock.find_lock(environ), str(current))

    def test_find_lock_is_none_with_no_lock(self):
        with tempfile.TemporaryDirectory() as scratch:
            self.assertIsNone(calibration_lock.find_lock({"HOME": scratch}))


class StampTest(unittest.TestCase):
    def test_format_stamp_round_trips_parse_stamp(self):
        stamp = "2026-10-01T10:00:00Z"
        self.assertEqual(calibration_lock.format_stamp(calibration_lock.parse_stamp(stamp)), stamp)

    def test_offset_form_does_not_parse(self):
        self.assertIsNone(calibration_lock.parse_stamp("2026-10-01T10:00:00+00:00"))


class LockViewTest(unittest.TestCase):
    def test_relative_file_is_joined_to_the_worktree_and_absolute_is_left_alone(self):
        relative = calibration_lock.read_lock_view('{"file": "src/a.ts", "worktree": "/work"}')
        absolute = calibration_lock.read_lock_view('{"file": "/other/a.ts", "worktree": "/work"}')
        self.assertEqual(relative.file, "/work/src/a.ts")
        self.assertEqual(absolute.file, "/other/a.ts")


class LockIsLiveTest(unittest.TestCase):
    def test_liveness_cases(self):
        now = time.time()
        fresh = calibration_lock.format_stamp(now)
        old = calibration_lock.format_stamp(now - calibration_lock.MUTATION_RUN_TIMEOUT_SECONDS - 60)
        cases = [
            ("dead owner", fresh, "99999999", False),
            ("fresh, no owner", fresh, "", True),
            ("past the timeout", old, "", False),
        ]
        for name, stamp, owner, expected in cases:
            with self.subTest(name):
                self.assertEqual(calibration_lock.lock_is_live(stamp, owner, now), expected)


if __name__ == "__main__":
    unittest.main()
