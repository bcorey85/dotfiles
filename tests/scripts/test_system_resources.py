"""Tests the memory, df and du readers in lib/system_resources.py."""
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths
from stubs import write_stub

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import system_resources

DF_TEXT = "Filesystem 1024-blocks Used Available Capacity Mounted on\n/dev/x 9999999 1 2097152 1% /\n"
VM_STAT_TEXT = ("Mach Virtual Memory Statistics: (page size of 16384 bytes)\n"
                "Pages free:                               65536.\n"
                "Pages active:                            999999.\n"
                "Pages inactive:                           32768.\n"
                "Pages speculative:                        16384.\n")


class ParseTest(unittest.TestCase):
    def test_meminfo_reads_mem_available_in_gb(self):
        text = "MemTotal: 99 kB\nMemAvailable:    2097152 kB\n"
        self.assertEqual(system_resources.parse_meminfo_gb(text), 2.0)

    def test_meminfo_without_the_line_is_none(self):
        self.assertIsNone(system_resources.parse_meminfo_gb("MemTotal: 99 kB\n"))

    def test_vm_stat_adds_free_inactive_and_speculative_pages(self):
        # (65536 + 32768 + 16384) pages of 16384 bytes = 1.75 GB
        self.assertEqual(system_resources.parse_vm_stat_gb(VM_STAT_TEXT, 16384), 1.75)

    def test_vm_stat_missing_a_page_kind_is_none(self):
        self.assertIsNone(system_resources.parse_vm_stat_gb("Pages free: 5.\n", 4096))


class CommandTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(os.path.realpath(scratch.name))
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        original_path = os.environ["PATH"]
        os.environ["PATH"] = f"{self.bin_dir}:{original_path}"
        self.addCleanup(os.environ.__setitem__, "PATH", original_path)

    def test_free_gb_reads_the_available_column_of_the_folder(self):
        write_stub(self.bin_dir / "df", f'echo "$1 $2" > "{self.root}/df-args"\nprintf %s "{DF_TEXT}"')

        gb = system_resources.free_gb(self.root)

        self.assertEqual(gb, 2.0)
        self.assertEqual((self.root / "df-args").read_text().strip(), f"-Pk {self.root}")

    def test_df_failure_raises_and_names_the_call(self):
        write_stub(self.bin_dir / "df", "exit 1")
        with self.assertRaisesRegex(system_resources.ResourceReadError, "df -Pk .* failed"):
            system_resources.free_gb(self.root)

    def test_df_without_a_figure_raises(self):
        write_stub(self.bin_dir / "df", "echo header")
        with self.assertRaises(system_resources.ResourceReadError):
            system_resources.free_gb(self.root)

    def test_tree_gb_reads_du_kilobytes(self):
        write_stub(self.bin_dir / "du", "printf '1048576\\t%s\\n' \"$2\"")
        self.assertEqual(system_resources.tree_gb(self.root), 1.0)

    def test_du_failure_raises(self):
        write_stub(self.bin_dir / "du", "exit 3")
        with self.assertRaises(system_resources.ResourceReadError):
            system_resources.tree_gb(self.root)

    def test_du_exit_1_with_a_total_is_accepted(self):
        write_stub(self.bin_dir / "du", "printf '1048576\\t%s\\n' \"$2\"\nexit 1")
        self.assertEqual(system_resources.tree_gb(self.root), 1.0)

    def test_du_exit_1_without_a_total_raises(self):
        write_stub(self.bin_dir / "du", "exit 1")
        with self.assertRaises(system_resources.ResourceReadError):
            system_resources.tree_gb(self.root)

    def test_an_unknown_platform_has_no_memory_reading(self):
        with mock.patch.object(system_resources.sys, "platform", "win32"):
            self.assertIsNone(system_resources.memory_available_gb())

    def test_macos_memory_combines_vm_stat_and_the_page_size(self):
        write_stub(self.bin_dir / "vm_stat", f"printf %s '{VM_STAT_TEXT}'")
        write_stub(self.bin_dir / "sysctl", "echo 16384")
        with mock.patch.object(system_resources.sys, "platform", "darwin"):
            self.assertEqual(system_resources.memory_available_gb(), 1.75)

    def test_macos_memory_is_none_when_sysctl_fails_or_prints_a_non_number(self):
        write_stub(self.bin_dir / "vm_stat", f"printf %s '{VM_STAT_TEXT}'")
        for body in ("exit 1", "echo many"):
            with self.subTest(body=body):
                write_stub(self.bin_dir / "sysctl", body)
                with mock.patch.object(system_resources.sys, "platform", "darwin"):
                    self.assertIsNone(system_resources.memory_available_gb())

    def test_macos_memory_is_none_when_vm_stat_fails(self):
        write_stub(self.bin_dir / "vm_stat", "exit 1")
        write_stub(self.bin_dir / "sysctl", "echo 16384")
        with mock.patch.object(system_resources.sys, "platform", "darwin"):
            self.assertIsNone(system_resources.memory_available_gb())


class SizeTextTest(unittest.TestCase):
    def test_size_text_picks_the_unit_at_each_threshold(self):
        cases = [
            (1024**3, "1.0 GB"),
            (3 * 1024**3 // 2, "1.5 GB"),
            (1024**3 - 1, "1024.0 MB"),
            (1024**2, "1.0 MB"),
            (1024**2 - 1, "1023 KB"),
            (1024, "1 KB"),
            (0, "0 KB"),
        ]
        for size, expected in cases:
            with self.subTest(size=size):
                self.assertEqual(system_resources.size_text(size), expected)


if __name__ == "__main__":
    unittest.main()
