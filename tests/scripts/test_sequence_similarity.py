"""Tests for sequence_similarity: bounded edit distance, n-gram counts and the multiset ratio."""
import sys
import unittest
from collections import Counter

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import sequence_similarity


def reference_distance(first, second):
    """Plain full-matrix Levenshtein distance."""
    rows = [list(range(len(second) + 1))]
    for row, item in enumerate(first, start=1):
        current = [row]
        for column, other in enumerate(second, start=1):
            current.append(min(rows[-1][column - 1] + (item != other), rows[-1][column] + 1, current[-1] + 1))
        rows.append(current)
    return rows[-1][-1]


class EditDistanceWithinTest(unittest.TestCase):
    def test_distance_within_the_limit_is_returned_and_beyond_it_is_none(self):
        cases = [
            ("same", "abcdef", "abcdef", 1, 0),
            ("one substitution", "abcdef", "abcxef", 1, 1),
            ("one insertion", "abcdef", "abcdxef", 1, 1),
            ("one deletion", "abcdef", "abcdf", 1, 1),
            ("two edits over a limit of one", "abcdef", "abxdxf", 1, None),
            ("two edits within a limit of two", "abcdef", "abxdxf", 2, 2),
            ("lengths too far apart", "abc", "abcdefg", 2, None),
            ("empty against one item", "", "a", 1, 1),
        ]
        for label, first, second, limit, expected in cases:
            with self.subTest(label):
                self.assertEqual(expected, sequence_similarity.edit_distance_within(list(first), list(second), limit))

    def test_it_agrees_with_the_full_matrix_distance_wherever_that_is_within_the_limit(self):
        words = ["", "a", "ab", "abc", "abcd", "badc", "aabb", "abcabc", "cba", "abxcd"]
        for first in words:
            for second in words:
                for limit in (1, 2, 3):
                    expected = reference_distance(first, second)
                    with self.subTest(first=first, second=second, limit=limit):
                        got = sequence_similarity.edit_distance_within(list(first), list(second), limit)
                        self.assertEqual(expected if expected <= limit else None, got)


class NgramAndMultisetTest(unittest.TestCase):
    def test_ngram_counts_count_each_run_of_neighbours(self):
        counts = sequence_similarity.ngram_counts(["a", "b", "a", "b"], 2)

        self.assertEqual(Counter({("a", "b"): 2, ("b", "a"): 1}), counts)

    def test_a_sequence_shorter_than_the_run_has_no_runs(self):
        self.assertEqual(Counter(), sequence_similarity.ngram_counts(["a"], 3))

    def test_similarity_is_one_for_equal_none_for_disjoint_and_a_ratio_between(self):
        same = sequence_similarity.multiset_similarity(Counter("aab"), Counter("baa"))
        disjoint = sequence_similarity.multiset_similarity(Counter("aa"), Counter("bb"))
        partial = sequence_similarity.multiset_similarity(Counter("aabb"), Counter("aacc"))

        self.assertEqual((1.0, 0.0, 0.5), (same, disjoint, partial))

    def test_two_empty_counts_are_the_same(self):
        self.assertEqual(1.0, sequence_similarity.multiset_similarity(Counter(), Counter()))


if __name__ == "__main__":
    unittest.main()
