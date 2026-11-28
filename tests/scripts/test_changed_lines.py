"""Checks for changed_lines.py. CHANGED_LINES_MODULE overrides the module path; it defaults to the installed one."""
import importlib.util
import os
import pathlib
import unittest
from types import SimpleNamespace

import toolkit_paths

MODULE = pathlib.Path(os.environ.get("CHANGED_LINES_MODULE") or toolkit_paths.LIB_DIR / "changed_lines.py")
module_spec = importlib.util.spec_from_file_location("changed_lines", MODULE)
changed_lines = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(changed_lines)


class ChangedLineSetsTest(unittest.TestCase):
    def test_diff_added_lines_and_every_untracked_line_count(self):
        hunk = SimpleNamespace(added=[(3, "x"), (4, "y")])
        diff_files = [SimpleNamespace(path="a.py", hunks=[hunk])]
        untracked = [SimpleNamespace(path="b.py", added_lines=[(1, "p"), (2, "q")])]

        changed = changed_lines.changed_line_sets(diff_files, untracked)

        self.assertEqual(changed, {"a.py": {3, 4}, "b.py": {1, 2}})

    def test_a_path_in_both_the_diff_and_the_untracked_entries_gets_the_union(self):
        hunk = SimpleNamespace(added=[(3, "x")])
        diff_files = [SimpleNamespace(path="a.py", hunks=[hunk])]
        untracked = [SimpleNamespace(path="a.py", added_lines=[(1, "p")])]

        changed = changed_lines.changed_line_sets(diff_files, untracked)

        self.assertEqual(changed, {"a.py": {1, 3}})


class RangeTest(unittest.TestCase):
    def test_touched_needs_one_changed_line_and_added_needs_every_line(self):
        changed = {"a.py": {3, 4, 5}}
        cases = [("a.py", 3, 5, True, True), ("a.py", 5, 6, True, False), ("a.py", 6, 7, False, False),
                 ("b.py", 1, 2, False, False)]
        for path, first, last, touched, added in cases:
            with self.subTest(path=path, first=first, last=last):
                self.assertEqual(changed_lines.range_touched(changed, path, first, last), touched)
                self.assertEqual(changed_lines.range_added(changed, path, first, last), added)


if __name__ == "__main__":
    unittest.main()
