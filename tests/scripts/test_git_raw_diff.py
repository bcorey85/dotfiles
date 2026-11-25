"""Checks for the one reader of `git diff --raw -z` output."""
import importlib.util
import os
import pathlib
import sys
import unittest

import toolkit_paths

MODULE = pathlib.Path(os.environ.get("GIT_RAW_DIFF_MODULE") or toolkit_paths.LIB_DIR / "git_raw_diff.py")
sys.path.insert(0, str(MODULE.parent))
module_spec = importlib.util.spec_from_file_location("git_raw_diff", MODULE)
git_raw_diff = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(git_raw_diff)


class RawEntriesTest(unittest.TestCase):
    def test_text_and_bytes_give_the_same_entries_and_a_rename_ends_at_its_new_path(self):
        raw = ":100644 100644 aaa bbb R100\0old.txt\0new.txt\0:160000 000000 ccc 000 D\0sub\0"

        from_text = git_raw_diff.raw_entries(raw)
        from_bytes = git_raw_diff.raw_entries(raw.encode())

        self.assertEqual([entry.path for entry in from_text], ["new.txt", "sub"])
        self.assertEqual(from_text[0].paths, ("old.txt", "new.txt"))
        self.assertEqual(from_text[1].old_mode, git_raw_diff.SUBMODULE_MODE)
        self.assertEqual([entry.path for entry in from_bytes], [b"new.txt", b"sub"])
        self.assertEqual(from_bytes[0].new_sha, "bbb", "the meta field is text even for bytes input")

    def test_a_malformed_entry_raises(self):
        with self.assertRaises(git_raw_diff.RawDiffError, msg="a meta field of the wrong shape"):
            git_raw_diff.raw_entries(":100644 aaa\0a.txt\0")
        with self.assertRaises(git_raw_diff.RawDiffError, msg="a rename that lacks its second path"):
            git_raw_diff.raw_entries(":100644 100644 aaa bbb R100\0old.txt\0")


if __name__ == "__main__":
    unittest.main()
