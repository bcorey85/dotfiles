"""Tests for path_summary.collapse_paths: a long path list folds by directory."""
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import path_summary


class CollapsePathsTest(unittest.TestCase):
    def test_a_short_list_is_returned_unchanged(self):
        paths = ["b.py", "a/c.py"]

        self.assertEqual(path_summary.collapse_paths(paths, 5), paths)

    def test_a_list_of_exactly_max_entries_is_returned_unchanged(self):
        paths = [f"a/f{index}.py" for index in range(5)]

        self.assertEqual(path_summary.collapse_paths(paths, 5), paths)

    def test_a_long_list_folds_the_big_directory_and_keeps_a_lone_file(self):
        cache = [f"evalset/blind/cache/intent/{index}.json" for index in range(6790)]
        paths = [*cache, "src/app.py", "docs/guide.md"]

        entries = path_summary.collapse_paths(paths, 10)

        self.assertEqual(entries, ["evalset/blind/cache/intent/ (6790 files)", "src/app.py", "docs/guide.md"])

    def test_a_list_spread_over_many_directories_folds_to_a_shallower_depth(self):
        paths = [f"top/dir{index}/sub/file.py" for index in range(30)]

        entries = path_summary.collapse_paths(paths, 10)

        self.assertEqual(entries, ["top/ (30 files)"])

    def test_top_level_files_fold_into_one_entry(self):
        paths = [f"file{index}.py" for index in range(12)]

        entries = path_summary.collapse_paths(paths, 5)

        self.assertEqual(entries, ["top-level files (12 files)"])

    def test_when_no_depth_fits_the_depth_one_fold_is_capped_with_an_and_more_entry(self):
        paths = [f"dir{directory}/file{number}.py" for directory in range(12) for number in range(2)]

        entries = path_summary.collapse_paths(paths, 5)

        self.assertEqual(entries, [*[f"dir{directory}/ (2 files)" for directory in range(5)], "and 7 more"])

    def test_when_no_depth_fits_the_cap_uses_the_depth_with_the_fewest_entries(self):
        deep = [f"a/y{directory}/f{number}.py" for directory in range(3) for number in range(20)]
        shallow = [f"b{index}/g.py" for index in range(3)]

        entries = path_summary.collapse_paths([*deep, *shallow], 4, never_fold=["a/x/mine.py"])

        self.assertEqual(entries, ["a/y0/ (20 files)", "a/y1/ (20 files)", "a/y2/ (20 files)", "b0/g.py", "and 2 more"])

    def test_files_each_alone_in_their_own_directory_are_capped_with_an_and_more_entry(self):
        paths = [f"dir{index}/file.py" for index in range(60)]

        entries = path_summary.collapse_paths(paths, 10)

        self.assertEqual(entries, [*paths[:10], "and 50 more"])

    def test_a_directory_with_a_never_fold_path_lists_its_files_one_by_one(self):
        shared = [f"shared/held{index}.py" for index in range(6)]
        other = [f"other/held{index}.py" for index in range(6)]

        entries = path_summary.collapse_paths([*shared, *other], 8, never_fold=["shared/mine.py"])

        self.assertEqual(entries, [*shared, "other/ (6 files)"])


if __name__ == "__main__":
    unittest.main()
