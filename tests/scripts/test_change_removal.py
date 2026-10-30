import importlib.util
import unittest
from collections import Counter

import toolkit_paths

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


class RemovalBlockerTest(unittest.TestCase):
    def test_the_blocker_names_the_counts_and_the_files_that_lost_the_most(self):
        added = {"a.py": Counter({f"a{n}": 1 for n in range(10)}), "b.py": Counter({f"b{n}": 1 for n in range(4)}),
                 "c.py": Counter({"c0": 1, "c1": 1})}
        removed = {"a.py": 6, "b.py": 3, "c.py": 1}

        blocker = change_removal.removal_blocker(added, removed)

        self.assertEqual("the fix passes removed 10 of the 16 source lines the change under review adds; "
                         "most lost in a.py (6), b.py (3), c.py (1)", blocker)
