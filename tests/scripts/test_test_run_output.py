import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import test_run_output

# The summary line each runner prints after a filtered run that ran at least one test.
PASSING_SUMMARIES = {
    "pytest": "===== 2 passed, 40 deselected in 0.31s =====",
    "vitest": " Test Files  1 passed (1)\n      Tests  2 passed | 5 skipped (7)",
    "jest": "Tests:       2 passed, 5 skipped, 7 total",
    "playwright": "  2 passed (3.1s)",
    "cargo": "test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 9 filtered out",
    "mocha": "  2 passing (12ms)",
    "bun": " 2 pass\n 0 fail\n 2 expect() calls",
    "go": "ok  \texample.com/orders\t0.012s",
}
# The output of a filtered run that exits 0 and ran no test.
NO_TEST_OUTPUTS = {
    "pytest": "===== 42 deselected in 0.20s =====",
    "vitest": " Test Files  1 skipped (1)\n      Tests  7 skipped (7)",
    "jest": "Tests:       7 skipped, 7 total",
    "cargo": "test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 11 filtered out",
    "mocha": "  0 passing (1ms)",
    "go": "ok  \texample.com/orders\t0.010s [no tests to run]",
}


class PassedTestCountTest(unittest.TestCase):
    def test_counts_the_passed_tests_in_each_runner_summary(self):
        for runner, summary in PASSING_SUMMARIES.items():
            with self.subTest(runner=runner):
                self.assertGreater(test_run_output.passed_test_count(summary), 0)

    def test_counts_none_when_the_filter_ran_no_test(self):
        for runner, output in NO_TEST_OUTPUTS.items():
            with self.subTest(runner=runner):
                self.assertEqual(0, test_run_output.passed_test_count(output))


class MatchesNoTestTest(unittest.TestCase):
    def test_a_filtered_mocha_run_that_passed_is_not_a_no_match(self):
        self.assertFalse(test_run_output.matches_no_test("npx mocha --grep totals", 0, PASSING_SUMMARIES["mocha"]))

    def test_a_filtered_bun_run_that_passed_is_not_a_no_match(self):
        self.assertFalse(test_run_output.matches_no_test("bun test -t totals", 0, PASSING_SUMMARIES["bun"]))

    def test_a_filtered_run_that_ran_no_test_is_a_no_match(self):
        self.assertTrue(test_run_output.matches_no_test("npx vitest run -t totals", 0, NO_TEST_OUTPUTS["vitest"]))

    def test_an_unfiltered_run_is_never_a_no_match(self):
        self.assertFalse(test_run_output.matches_no_test("npx vitest run", 0, NO_TEST_OUTPUTS["vitest"]))

    def test_a_failing_run_is_never_a_no_match(self):
        self.assertFalse(test_run_output.matches_no_test("npx vitest run -t totals", 1, NO_TEST_OUTPUTS["vitest"]))


if __name__ == "__main__":
    unittest.main()
