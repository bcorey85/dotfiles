import importlib.util
import pathlib
import unittest

import toolkit_paths

module_spec = importlib.util.spec_from_file_location("numstat", toolkit_paths.LIB_DIR / "numstat.py")
numstat = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(numstat)

NUMSTAT = "12\t3\tsrc/a/one.py\n30\t0\tsrc/a/two.py\n5\t5\tsrc/b/three.py\n-\t-\tlogo.png\n7\t0\tlock.json\n"


class AddedLinesByGroupTest(unittest.TestCase):
    def test_added_lines_are_summed_per_group_and_binary_and_skipped_files_count_nowhere(self):
        totals = numstat.added_lines_by_group(NUMSTAT, lambda path: str(pathlib.PurePosixPath(path).parent),
                                              lambda path: path == "lock.json")

        self.assertEqual({"src/a": 42, "src/b": 5}, totals)

    def test_empty_text_gives_no_groups(self):
        self.assertEqual({}, numstat.added_lines_by_group("", lambda path: path))


if __name__ == "__main__":
    unittest.main()
