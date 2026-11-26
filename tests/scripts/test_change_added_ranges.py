import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
module_spec = importlib.util.spec_from_file_location("change_added_ranges",
                                                     toolkit_paths.LIB_DIR / "change_added_ranges.py")
change_added_ranges = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(change_added_ranges)


class ChangeAddedRangesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = pathlib.Path(self.temp.name)
        self.git("init", "-q", "-b", "main")
        (self.repo / "tracked.py").write_text("a = 1\n")
        self.git("add", ".")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base")
        (self.repo / "tracked.py").write_text("a = 1\nb = 2\n")
        (self.repo / "new.py").write_text("c = 3\n")
        (self.repo / "blob.bin").write_bytes(b"\0\1\2")
        os.symlink("tracked.py", self.repo / "link.py")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)

    def test_untracked_files_count_whole_and_a_tracked_file_keeps_its_added_lines(self):
        added = change_added_ranges.change_added_ranges(self.repo)

        self.assertEqual([(2, 2)], added["tracked.py"])
        for name in ("new.py", "blob.bin", "link.py"):
            self.assertEqual(change_added_ranges.WHOLE_FILE, added[name], name)

    def test_text_only_leaves_out_an_untracked_binary_and_symlink(self):
        added = change_added_ranges.change_added_ranges(self.repo, text_only=True)

        self.assertEqual({"tracked.py", "new.py"}, set(added))

    def test_relative_reads_diff_paths_from_a_subfolder(self):
        folder = self.repo / "sub"
        folder.mkdir()
        (folder / "inner.py").write_text("a = 1\n")
        self.git("add", ".")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "inner")
        (folder / "inner.py").write_text("a = 1\nb = 2\n")
        (self.repo / "tracked.py").write_text("a = 1\nb = 2\nc = 3\n")

        plain = change_added_ranges.change_added_ranges(folder)
        relative = change_added_ranges.change_added_ranges(folder, relative=True)

        self.assertIn("sub/inner.py", plain)
        self.assertEqual([(2, 2)], relative["inner.py"])
        self.assertNotIn("sub/inner.py", relative)
        self.assertIn("tracked.py", plain)
        self.assertNotIn("tracked.py", relative)

    def test_no_renames_reads_a_renamed_file_as_added_whole(self):
        (self.repo / "tracked.py").write_text("a = 1\n" * 5)
        self.git("add", ".")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "five")
        self.git("mv", "tracked.py", "moved.py")

        with_renames = change_added_ranges.change_added_ranges(self.repo, detect_renames=True)
        without = change_added_ranges.change_added_ranges(self.repo, no_renames=True)

        self.assertNotIn("moved.py", with_renames)
        self.assertEqual([(1, 5)], without["moved.py"])

    def test_a_repo_with_no_commit_gives_none(self):
        empty = pathlib.Path(self.temp.name) / "empty"
        empty.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=empty, check=True)

        self.assertIsNone(change_added_ranges.change_added_ranges(empty))


if __name__ == "__main__":
    unittest.main()
