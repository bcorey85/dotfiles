"""index_export: a folder of the git index written out, and the absolute path of the index in use."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import index_export


class IndexExportTests(unittest.TestCase):
    def setUp(self):
        folders = [tempfile.TemporaryDirectory() for _ in range(2)]
        for folder in folders:
            self.addCleanup(folder.cleanup)
        self.repo, self.out = (pathlib.Path(folder.name) for folder in folders)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)

    def stage(self, relative_path, text):
        target = self.repo / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        subprocess.run(["git", "add", relative_path], cwd=self.repo, check=True)

    def test_the_folder_comes_out_as_the_index_holds_it_not_the_work_tree(self):
        self.stage("dir/a.txt", "staged\n")
        (self.repo / "dir" / "a.txt").write_text("unstaged edit\n", encoding="utf-8")
        self.stage("other/b.txt", "outside\n")
        root = index_export.export_index_folder(self.repo, "dir", self.out)
        self.assertEqual((root / "a.txt").read_text(), "staged\n")
        self.assertFalse((self.out / "other").exists())

    def test_nested_folders_and_names_with_spaces_or_newlines_come_out(self):
        self.stage("dir/sub dir/a b.txt", "spaced\n")
        self.stage("dir/odd\nname.txt", "newline\n")
        root = index_export.export_index_folder(self.repo, "dir", self.out)
        self.assertEqual((root / "sub dir" / "a b.txt").read_text(), "spaced\n")
        self.assertEqual((root / "odd\nname.txt").read_text(), "newline\n")

    def test_a_folder_with_no_indexed_file_exports_nothing(self):
        root = index_export.export_index_folder(self.repo, "dir", self.out)
        self.assertFalse(root.exists())

    def test_the_named_index_is_made_absolute_else_the_git_dir_index_is_used(self):
        git_dir = self.repo / ".git"
        with mock.patch.dict(os.environ, {"GIT_INDEX_FILE": "rel-index"}):
            self.assertEqual(index_export.index_file_path(git_dir), pathlib.Path("rel-index").resolve())
        with mock.patch.dict(os.environ):
            os.environ.pop("GIT_INDEX_FILE", None)
            self.assertEqual(index_export.index_file_path(git_dir), git_dir / "index")


if __name__ == "__main__":
    unittest.main()
