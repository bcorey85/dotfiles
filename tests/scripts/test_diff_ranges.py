"""lib/diff_ranges.py: the test of whether a span of lines touches or is covered by a list of (first, last) ranges."""
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import diff_ranges


class RangeListTest(unittest.TestCase):
    def test_ranges_touch_and_cover_a_span(self):
        ranges = [(3, 5), (6, 8), (20, 25)]
        cases = [
            ("covered across two adjacent ranges", 4, 7, True, True),
            ("covered inside one range", 21, 22, True, True),
            ("gap breaks cover but touches", 7, 10, True, False),
            ("outside every range", 10, 15, False, False),
            ("overlaps the start of a range", 1, 3, True, False),
            ("starts on a range's last line", 8, 10, True, False),
            ("starts one line past a range", 9, 10, False, False),
            ("ends one line past the last range", 22, 26, True, False),
            ("ends on the last line of a range", 3, 5, True, True),
            ("ends on the last line of the final range", 20, 25, True, True),
        ]
        for message, first, last, touches, covers in cases:
            self.assertEqual(touches, diff_ranges.ranges_touch(ranges, first, last), message)
            self.assertEqual(covers, diff_ranges.ranges_cover(ranges, first, last), message)

    def test_cover_reads_unsorted_and_overlapping_ranges(self):
        cases = [
            ("unsorted adjacent ranges", [(6, 8), (3, 5)], 4, 7),
            ("a range inside an earlier one", [(3, 10), (4, 6)], 3, 10),
            ("a whole-file range", [(1, sys.maxsize)], 40, 60),
        ]
        for message, ranges, first, last in cases:
            self.assertTrue(diff_ranges.ranges_cover(ranges, first, last), message)

    def test_no_ranges_touch_and_cover_nothing(self):
        self.assertFalse(diff_ranges.ranges_touch([], 1, 2))
        self.assertFalse(diff_ranges.ranges_cover([], 1, 2))


if __name__ == "__main__":
    unittest.main()
