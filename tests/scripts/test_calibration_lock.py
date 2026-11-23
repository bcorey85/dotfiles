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


if __name__ == "__main__":
    unittest.main()
