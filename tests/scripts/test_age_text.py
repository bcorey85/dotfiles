"""lib/age_text.py: a span of seconds as a short age."""
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
from age_text import age_text


class AgeTextTest(unittest.TestCase):
    def test_a_span_reads_as_its_largest_whole_unit(self):
        cases = {-5: "under 1m", 0: "under 1m", 59: "under 1m", 60: "1m", 3599: "59m", 3600: "1h",
                 86399: "23h", 86400: "1d", 7 * 86400 + 5: "7d"}
        for seconds, expected in cases.items():
            with self.subTest(seconds=seconds):
                self.assertEqual(age_text(seconds), expected)


if __name__ == "__main__":
    unittest.main()
