"""Checks for file_backup.py, which saves files before a step and puts back the ones that vanished."""
import pathlib
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import file_backup


class FileBackupTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(scratch.name)

    def test_a_deleted_file_comes_back_with_its_bytes_and_a_kept_file_is_untouched(self):
        (self.root / "sub").mkdir()
        (self.root / "sub" / "a.sql").write_bytes(b"select 1;\n")
        (self.root / "b.sql").write_text("kept")
        backup = file_backup.save_files(self.root, ["sub/a.sql", "b.sql"])
        (self.root / "sub" / "a.sql").unlink()
        (self.root / "sub").rmdir()

        restored, lost = file_backup.restore_missing(backup)

        self.assertEqual((restored, lost), (["sub/a.sql"], []))
        self.assertEqual((self.root / "sub" / "a.sql").read_bytes(), b"select 1;\n")
        self.assertEqual((self.root / "b.sql").read_text(), "kept")

    def test_a_file_an_edit_changed_is_not_overwritten(self):
        (self.root / "a.sql").write_text("old")
        backup = file_backup.save_files(self.root, ["a.sql"])
        (self.root / "a.sql").write_text("new")

        self.assertEqual(file_backup.restore_missing(backup), ([], []))
        self.assertEqual((self.root / "a.sql").read_text(), "new")

    def test_files_over_a_cap_are_left_unsaved_and_reported_lost_when_gone(self):
        cases = [
            ("one file over the per-file cap", {"max_file_bytes": 4, "max_total_bytes": 100}, ["big.sql"],
             ["small.sql"]),
            ("files over the total cap", {"max_file_bytes": 100, "max_total_bytes": 7}, ["small.sql"],
             ["big.sql"]),
        ]
        for message, caps, expected_unsaved, expected_restored in cases:
            with self.subTest(message):
                (self.root / "big.sql").write_text("123456")
                (self.root / "small.sql").write_text("12")
                backup = file_backup.save_files(self.root, ["big.sql", "small.sql"], **caps)
                (self.root / "big.sql").unlink()
                (self.root / "small.sql").unlink()

                restored, lost = file_backup.restore_missing(backup)

                self.assertEqual(backup.unsaved, expected_unsaved)
                self.assertEqual(lost, expected_unsaved)
                self.assertEqual(restored, expected_restored)
                for name in expected_unsaved:
                    self.assertFalse((self.root / name).exists())
                for name in expected_restored:
                    (self.root / name).unlink()


if __name__ == "__main__":
    unittest.main()
