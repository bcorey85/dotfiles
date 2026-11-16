"""Checks for shell_write_paths.py (the path a write target names, and whether git tracks it)."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))

from shell_write_paths import is_git_tracked, is_stream_or_device, resolve_target


class ResolveTargetTest(unittest.TestCase):
    def test_a_word_that_is_no_file_resolves_to_none(self):
        for word in ("&1", "-foo", "/dev/null", "", "'/dev/stderr'"):
            self.assertIsNone(resolve_target(word, "/work"), word)

    def test_a_dev_prefix_followed_by_dot_dot_is_a_file(self):
        self.assertEqual(resolve_target("/dev/../home/x", "/work"), "/dev/../home/x")

    def test_a_relative_target_joins_the_cwd_and_an_absolute_one_stays(self):
        self.assertEqual(resolve_target("a/b.txt", "/work"), "/work/a/b.txt")
        self.assertEqual(resolve_target("/tmp/b.txt", "/work"), "/tmp/b.txt")

    def test_stream_or_device_words(self):
        self.assertTrue(is_stream_or_device("&2"))
        self.assertTrue(is_stream_or_device("/dev/shm/x"))
        self.assertFalse(is_stream_or_device("/dev/../home/x"))
        self.assertFalse(is_stream_or_device("dev/x"))


class IsGitTrackedTest(unittest.TestCase):
    def test_tracked_untracked_and_missing_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder)
            subprocess.run(["git", "-C", folder, "init", "-q"], check=True)
            tracked = repo / "tracked.txt"
            tracked.write_text("x")
            (repo / "loose.txt").write_text("x")
            subprocess.run(["git", "-C", folder, "add", "tracked.txt"], check=True)
            self.assertTrue(is_git_tracked(str(tracked)))
            self.assertFalse(is_git_tracked(str(repo / "loose.txt")))
            self.assertFalse(is_git_tracked(str(repo / "no_such_folder" / "f.txt")))


if __name__ == "__main__":
    unittest.main()
