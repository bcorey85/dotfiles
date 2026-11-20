"""Checks for file_backup.py, which copies files to disk before a step and puts back the ones that vanished."""
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
        self.root = pathlib.Path(scratch.name) / "tree"
        self.root.mkdir()
        self.backup_dir = pathlib.Path(scratch.name) / "backup"

    def save(self, paths, **options):
        return file_backup.save_files(self.root, paths, self.backup_dir, **options)

    def test_a_deleted_file_comes_back_with_its_bytes_and_a_kept_file_is_untouched(self):
        (self.root / "sub").mkdir()
        (self.root / "sub" / "a.sql").write_bytes(b"select 1;\n")
        (self.root / "b.sql").write_text("kept")
        backup = self.save(["sub/a.sql", "b.sql"])
        (self.root / "sub" / "a.sql").unlink()
        (self.root / "sub").rmdir()

        restored, lost = file_backup.restore_missing(backup)

        self.assertEqual((restored, lost), (["sub/a.sql"], []))
        self.assertEqual((self.root / "sub" / "a.sql").read_bytes(), b"select 1;\n")
        self.assertEqual((self.root / "b.sql").read_text(), "kept")

    def test_restore_changed_puts_back_an_edited_and_a_deleted_file_with_its_mode(self):
        (self.root / "sub").mkdir()
        script = self.root / "sub" / "run.sh"
        script.write_text("echo hi\n")
        script.chmod(0o755)
        (self.root / "b.txt").write_text("old")
        backup = self.save(["sub/run.sh", "b.txt"])
        (self.root / "b.txt").write_text("new")
        script.unlink()
        (self.root / "sub").rmdir()

        restored = file_backup.restore_changed(backup)

        self.assertEqual(restored, ["b.txt", "sub/run.sh"])
        self.assertEqual((self.root / "b.txt").read_text(), "old")
        self.assertEqual(script.read_text(), "echo hi\n")
        self.assertEqual(script.stat().st_mode & 0o777, 0o755)

    def test_a_file_an_edit_changed_is_not_overwritten(self):
        (self.root / "a.sql").write_text("old")
        backup = self.save(["a.sql"])
        (self.root / "a.sql").write_text("new")

        self.assertEqual(file_backup.restore_missing(backup), ([], []))
        self.assertEqual((self.root / "a.sql").read_text(), "new")

    def test_a_one_megabyte_file_is_copied_to_disk_and_restored(self):
        content = b"x" * (1024 * 1024)
        (self.root / "big.bin").write_bytes(content)
        backup = self.save(["big.bin"])
        (self.root / "big.bin").unlink()

        restored, lost = file_backup.restore_missing(backup)

        self.assertEqual((restored, lost), (["big.bin"], []))
        self.assertEqual((self.root / "big.bin").read_bytes(), content)
        self.assertEqual((self.backup_dir / "big.bin").read_bytes(), content)

    def test_only_a_file_over_the_cap_is_left_unsaved_and_reported_lost_when_gone(self):
        (self.root / "big.sql").write_text("123456")
        (self.root / "small.sql").write_text("12")
        backup = self.save(["big.sql", "small.sql"], max_file_bytes=4)
        (self.root / "big.sql").unlink()
        (self.root / "small.sql").unlink()

        restored, lost = file_backup.restore_missing(backup)

        self.assertEqual(backup.unsaved, ["big.sql"])
        self.assertEqual((restored, lost), (["small.sql"], ["big.sql"]))
        self.assertFalse((self.root / "big.sql").exists())

    def test_discard_removes_the_copies(self):
        (self.root / "a.sql").write_text("old")
        backup = self.save(["a.sql"])

        file_backup.discard(backup)

        self.assertFalse(self.backup_dir.exists())


if __name__ == "__main__":
    unittest.main()
