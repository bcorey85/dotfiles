import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest
from collections import Counter

import toolkit_paths

sys.path[:0] = [str(toolkit_paths.REVIEW_DIR), str(toolkit_paths.LIB_DIR)]
review_loop_plan = importlib.import_module("review_loop_plan")

module_spec = importlib.util.spec_from_file_location("change_removal", toolkit_paths.LIB_DIR / "change_removal.py")
change_removal = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(change_removal)


def numbered(count, prefix="line"):
    return "".join(f"{prefix} {number}\n" for number in range(count))


def gutted_after(old_texts, new_texts, current_texts):
    """(removed by file, whether gutted) for changes from old_texts to new_texts, once the tree holds current_texts."""
    added = {path: change_removal.added_lines(old_texts.get(path, ""), text) for path, text in new_texts.items()}
    current_added = {path: change_removal.added_lines(old_texts.get(path, ""), text)
                     for path, text in current_texts.items()}
    removed = change_removal.removed_by_file(added, current_added)
    return removed, change_removal.is_gutted(added, removed)


class AddedLinesTest(unittest.TestCase):
    def test_blank_lines_and_surrounding_whitespace_do_not_count(self):
        added = change_removal.added_lines("keep\n", "keep\n\n   \n  new  \n")

        self.assertEqual(Counter({"new": 1}), added)

    def test_a_repeated_line_counts_only_the_copies_the_change_added(self):
        added = change_removal.added_lines("x\n", "x\nx\nx\n")

        self.assertEqual(Counter({"x": 2}), added)


class GuttedChangeTest(unittest.TestCase):
    def test_half_of_ten_added_lines_removed_is_gutted_and_four_is_not(self):
        new_texts = {"app.py": numbered(10)}
        cases = [
            ("five of ten", numbered(5), True),
            ("four of ten", numbered(6), False),
            ("all of ten", "", True),
        ]
        for message, current, expected in cases:
            with self.subTest(message):
                _removed, gutted = gutted_after({}, new_texts, {"app.py": current})

                self.assertEqual(expected, gutted)

    def test_a_change_under_ten_lines_is_never_gutted(self):
        _removed, gutted = gutted_after({}, {"app.py": numbered(9)}, {"app.py": ""})

        self.assertFalse(gutted)

    def test_a_line_removed_and_added_back_unchanged_is_not_removed(self):
        new_texts = {"app.py": numbered(10)}
        current = numbered(10)

        removed, gutted = gutted_after({}, new_texts, {"app.py": current})

        self.assertEqual(({}, False), (removed, gutted))

    def test_a_line_moved_within_its_file_is_not_removed(self):
        lines = numbered(10).splitlines()
        reordered = "\n".join(reversed(lines)) + "\n"

        removed, _gutted = gutted_after({}, {"app.py": numbered(10)}, {"app.py": reordered})

        self.assertEqual({}, removed)

    def test_lines_moved_into_another_file_are_not_removed(self):
        removed, gutted = gutted_after({}, {"app.py": numbered(10)}, {"lib/helper.py": numbered(10)})

        self.assertEqual(({}, False), (removed, gutted))

    def test_a_line_two_files_added_is_kept_once_when_one_copy_survives(self):
        new_texts = {"a.py": "x\n" * 6, "b.py": "x\n" * 6}
        current_texts = {"a.py": "x\n" * 6}

        removed, gutted = gutted_after({}, new_texts, current_texts)

        self.assertEqual(6, sum(removed.values()))
        self.assertTrue(gutted)

    def test_blank_lines_in_the_added_text_are_ignored_when_counting_the_bars(self):
        padded = "".join(f"line {number}\n\n" for number in range(9))

        _removed, gutted = gutted_after({}, {"app.py": padded}, {"app.py": ""})

        self.assertFalse(gutted)

    def test_removal_is_cumulative_over_two_passes(self):
        new_texts = {"app.py": numbered(10)}
        after_first_pass = {"app.py": numbered(10).replace("line 0\nline 1\nline 2\n", "")}
        after_second_pass = {"app.py": numbered(5)}

        first_removed, first_gutted = gutted_after({}, new_texts, after_first_pass)
        second_removed, second_gutted = gutted_after({}, new_texts, after_second_pass)

        self.assertEqual(({"app.py": 3}, False), (first_removed, first_gutted))
        self.assertEqual(({"app.py": 5}, True), (second_removed, second_gutted))

    def test_a_file_missing_from_the_tree_lost_all_its_added_lines(self):
        removed, _gutted = gutted_after({}, {"app.py": numbered(4)}, {})

        self.assertEqual({"app.py": 4}, removed)

    def test_lines_the_head_already_held_are_not_part_of_the_change(self):
        old_texts = {"app.py": numbered(10)}
        new_texts = {"app.py": numbered(10) + numbered(10, "extra")}

        removed, gutted = gutted_after(old_texts, new_texts, {"app.py": numbered(10)})

        self.assertEqual(({"app.py": 10}, True), (removed, gutted))

    def test_a_removed_line_the_head_already_holds_elsewhere_in_the_file_is_still_removed(self):
        old_texts = {"app.py": "x\n" * 3}
        new_texts = {"app.py": "x\n" * 5 + numbered(10)}
        current_texts = {"app.py": "x\n" * 3 + "tweak\n"}

        removed, gutted = gutted_after(old_texts, new_texts, current_texts)

        self.assertEqual(({"app.py": 12}, True), (removed, gutted))


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


class MovedByFixTest(unittest.TestCase):
    def test_lines_the_fix_added_to_a_file_that_already_held_them_are_kept(self):
        finder = ["start = None", "for row in rows:", "    if row:", "        start = row", "return start"]
        added = {"edit.py": change_removal.added_lines("", "\n".join(finder) + "\n")}
        current_added = {}
        fix_added = {"dates.py": Counter(line.strip() for line in finder)}

        removed = change_removal.removed_by_file(added, current_added, fix_added)

        self.assertEqual({}, removed)

    def test_copies_kept_in_different_files_by_the_two_bases_add_up(self):
        block = numbered(10)
        added = {"edit.py": change_removal.added_lines("", block), "a.py": change_removal.added_lines("", block)}
        current_added = {"a.py": change_removal.added_lines("", block)}
        fix_added = {"dates.py": change_removal.added_lines("", block)}

        removed = change_removal.removed_by_file(added, current_added, fix_added)

        self.assertEqual({}, removed)
        self.assertFalse(change_removal.is_gutted(added, removed))

    def test_lines_the_fix_deleted_without_adding_them_elsewhere_stay_removed(self):
        added = {"edit.py": change_removal.added_lines("", numbered(10))}
        fix_added = {"dates.py": change_removal.added_lines("", numbered(3, "other"))}

        removed = change_removal.removed_by_file(added, {}, fix_added)

        self.assertEqual({"edit.py": 10}, removed)


class ChangeUnderReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = pathlib.Path(self.tmp.name)
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "T")
        self.block = numbered(10, "finder")
        self.write("dates.py", "import datetime\n" + self.block)
        self.write("edit.py", "import edit_base\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "base")
        # The change under review moves the block from dates.py into edit.py.
        self.write("dates.py", "import datetime\n")
        self.write("edit.py", "import edit_base\n" + self.block)

    def write(self, name, text):
        (self.repo / name).write_text(text)

    def test_a_block_a_fix_pass_moves_back_into_the_file_it_left_is_not_removed(self):
        change = review_loop_plan.ChangeUnderReview(str(self.repo))
        self.write("dates.py", "import datetime\n" + self.block)
        self.write("edit.py", "import edit_base\n")

        self.assertEqual({}, change.removed())

    def test_a_block_moved_after_a_commit_made_during_the_loop_is_not_removed(self):
        change = review_loop_plan.ChangeUnderReview(str(self.repo))
        git(self.repo, "commit", "-q", "-am", "mid-loop")
        self.write("dates.py", "import datetime\n" + self.block)
        self.write("edit.py", "import edit_base\n")
        git(self.repo, "commit", "-q", "-am", "pass")

        self.assertEqual({}, change.removed())

    def test_a_block_a_fix_pass_deletes_is_removed(self):
        change = review_loop_plan.ChangeUnderReview(str(self.repo))
        self.write("edit.py", "import edit_base\n")

        self.assertEqual({"edit.py": 10}, change.removed())


class RemovalBlockerTest(unittest.TestCase):
    def test_the_blocker_names_the_counts_and_the_files_that_lost_the_most(self):
        added = {"a.py": Counter({f"a{n}": 1 for n in range(10)}), "b.py": Counter({f"b{n}": 1 for n in range(4)}),
                 "c.py": Counter({"c0": 1, "c1": 1})}
        removed = {"a.py": 6, "b.py": 3, "c.py": 1}

        blocker = change_removal.removal_blocker(added, removed)

        self.assertEqual("the fix passes removed 10 of the 16 source lines the change under review adds; "
                         "most lost in a.py (6), b.py (3), c.py (1)", blocker)
