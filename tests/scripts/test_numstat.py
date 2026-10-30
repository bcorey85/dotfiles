import importlib.util
import pathlib
import unittest

import toolkit_paths

module_spec = importlib.util.spec_from_file_location("numstat", toolkit_paths.LIB_DIR / "numstat.py")
numstat = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(numstat)

NUMSTAT = (
    "12\t3\tsrc/a/one.py\0" "30\t0\tsrc/a/two.py\0" "5\t5\tsrc/b/three.py\0" "-\t-\tlogo.png\0" "7\t0\tlock.json\0"
)


class NumstatRowsTest(unittest.TestCase):
    def test_a_plain_row_gives_its_counts_and_path(self):
        self.assertEqual([(12, 3, "src/a/one.py")], list(numstat.numstat_rows("12\t3\tsrc/a/one.py\0")))

    def test_a_binary_row_gives_no_counts(self):
        self.assertEqual([(None, None, "logo.png")], list(numstat.numstat_rows("-\t-\tlogo.png\0")))

    def test_a_rename_row_gives_its_new_path(self):
        text = "2\t1\t\0src/old.py\0src/new.py\0" "3\t0\tplain.py\0"

        self.assertEqual([(2, 1, "src/new.py"), (3, 0, "plain.py")], list(numstat.numstat_rows(text)))


class AddedLinesByGroupTest(unittest.TestCase):
    def test_added_lines_are_summed_per_group_and_binary_and_skipped_files_count_nowhere(self):
        totals = numstat.added_lines_by_group(NUMSTAT, lambda path: str(pathlib.PurePosixPath(path).parent),
                                              lambda path: path == "lock.json")

        self.assertEqual({"src/a": 42, "src/b": 5}, totals)

    def test_a_renamed_file_counts_under_its_new_path(self):
        text = ("0\t0\t\0old.py\0new.py\0"
                "2\t1\t\0src/old/mod.py\0src/new/mod.py\0"
                "3\t0\tplain.py\0")

        self.assertEqual({"new.py": (0, 0), "src/new/mod.py": (2, 1), "plain.py": (3, 0)},
                         numstat.changed_lines_by_path(text))

    def test_paths_with_odd_characters_come_back_exactly(self):
        text = ("1\t0\ta b => c.py\0"
                "2\t0\tq\"uote.py\0"
                "4\t0\tdir/{x => y}/f.py\0"
                "5\t0\t\0old name.py\0new => name.py\0")

        self.assertEqual({"a b => c.py": (1, 0), "q\"uote.py": (2, 0), "dir/{x => y}/f.py": (4, 0),
                          "new => name.py": (5, 0)}, numstat.changed_lines_by_path(text))

    def test_empty_text_gives_no_groups(self):
        self.assertEqual({}, numstat.added_lines_by_group("", lambda path: path))


if __name__ == "__main__":
    unittest.main()
