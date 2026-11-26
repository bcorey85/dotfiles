"""Tests for the untracked-file listing of a work tree."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import untracked_listing


class UntrackedListingTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def test_each_kind_of_untracked_entry_is_classified(self):
        (self.root / "text.py").write_text("a = 1\nb = 2\n")
        (self.root / "blob.bin").write_bytes(b"\xff\x00\xfe")
        os.symlink("text.py", self.root / "link.py")

        entries = {entry.path: entry for entry in untracked_listing.untracked_files(self.root)}

        self.assertEqual([(1, "a = 1"), (2, "b = 2")], entries["text.py"].added_lines)
        self.assertEqual("", entries["text.py"].kind)
        self.assertEqual(untracked_listing.change_added_ranges.UNTRACKED_BINARY, entries["blob.bin"].kind)
        self.assertEqual(untracked_listing.change_added_ranges.UNTRACKED_SYMLINK, entries["link.py"].kind)

    def test_a_git_failure_raises_the_listing_error(self):
        with (mock.patch.object(untracked_listing.script_utils, "untracked_paths", return_value=None),
              self.assertRaises(untracked_listing.UntrackedListError)):
            untracked_listing.untracked_files(self.root)


if __name__ == "__main__":
    unittest.main()
