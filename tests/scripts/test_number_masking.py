import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import number_masking


class NumberMaskingTest(unittest.TestCase):
    def test_lines_that_differ_only_in_numbers_mask_equal(self):
        first = "FAILED t.py::a - HTTP 429 retry after 12s at 10:01:02"
        second = "FAILED t.py::a - HTTP 429 retry after 7s at 11:59:48"

        self.assertEqual(number_masking.masked_numbers(first), number_masking.masked_numbers(second))

    def test_each_run_of_digits_becomes_one_hash(self):
        self.assertEqual("HTTP # retry after #s", number_masking.masked_numbers("HTTP 429 retry after 12s"))

    def test_lines_that_differ_in_words_stay_different(self):
        first = number_masking.masked_numbers("FAILED t.py::a - HTTP 429")
        second = number_masking.masked_numbers("FAILED t.py::b - HTTP 429")

        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
