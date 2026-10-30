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
    def test_a_runner_inside_a_command_substitution_is_not_judged(self):
        dollar = "test \"$(env CARGO_BUILD_JOBS=4 cargo test fault_codes -- --exact 2>&1 | rg -c 'ok')\" = 2"
        backtick = "test \"`cargo test fault_codes -- --exact 2>&1 | rg -c ok`\" = 2"
        for command in (dollar, backtick):
            with self.subTest(command=command):
                self.assertFalse(test_run_output.matches_no_test(command, 0, ""))

    def test_a_runner_piped_into_another_command_is_not_judged(self):
        commands = [
            "cargo test --lib totals 2>&1 | rg -q 'test result: ok\\. 25 passed'",
            "cargo test --lib totals |& rg -q 25",
            "pytest -k totals | tail -1",
            "npx vitest run -t totals | grep -q passed",
            "npx jest --testNamePattern totals | rg -q passed",
            "cd app && cargo test totals | rg -q passed && echo ok",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.assertFalse(test_run_output.matches_no_test(command, 0, ""))

    def test_a_runner_after_a_pipeline_is_still_judged(self):
        commands = ["echo go | cat && cargo test totals", "ls | wc -l; npx vitest run -t totals"]
        for command in commands:
            with self.subTest(command=command):
                self.assertTrue(test_run_output.matches_no_test(command, 0, ""))

    def test_a_filtered_mocha_or_bun_run_that_passed_is_not_a_no_match(self):
        runs = (("npx mocha --grep totals", "mocha"), ("bun test -t totals", "bun"))
        for command, runner in runs:
            with self.subTest(runner=runner):
                self.assertFalse(test_run_output.matches_no_test(command, 0, PASSING_SUMMARIES[runner]))

    def test_a_filtered_run_that_ran_no_test_is_a_no_match(self):
        self.assertTrue(test_run_output.matches_no_test("npx vitest run -t totals", 0, NO_TEST_OUTPUTS["vitest"]))

    def test_a_python_module_run_of_pytest_is_no_filter_even_when_every_test_skipped(self):
        for command in ("python -m pytest", "python3 -m pytest tests"):
            with self.subTest(command=command):
                self.assertFalse(test_run_output.matches_no_test(command, 0, "===== 3 skipped in 0.12s ====="))

    def test_an_unfiltered_run_is_never_a_no_match(self):
        self.assertFalse(test_run_output.matches_no_test("npx vitest run", 0, NO_TEST_OUTPUTS["vitest"]))

    def test_a_failing_run_is_never_a_no_match(self):
        self.assertFalse(test_run_output.matches_no_test("npx vitest run -t totals", 1, NO_TEST_OUTPUTS["vitest"]))

    def test_a_cargo_test_name_after_option_flags_is_a_filter_and_bare_options_are_not(self):
        rows = [
            ("cargo test --test billing totals", True),
            ("cargo test -p ledger --test billing totals", True),
            ("cargo test --test billing -- totals", True),
            ("cargo test --release --lib totals", True),
            ("cargo test --test billing", False),
            ("cargo test -p ledger --test billing --release", False),
            ("cargo test", False),
        ]
        for command, is_filter in rows:
            with self.subTest(command=command):
                self.assertEqual(is_filter, test_run_output.matches_no_test(command, 0, NO_TEST_OUTPUTS["cargo"]))

    def test_each_runners_own_summary_line_is_read(self):
        outputs = {
            "pytest": ("noise\n===== 3 failed, 4000 passed in 41.20s (0:00:41) =====\n",
                       "3 failed, 4000 passed in 41.20s"),
            "pytest quiet": ("4 passed in 0.31s\n", "4 passed in 0.31s"),
            "unittest": ("....\nRan 12 tests in 0.004s\n\nOK\n", "Ran 12 tests in 0.004s: OK"),
            "django failed": ("Ran 5 tests in 1.2s\n\nFAILED (failures=2)\n",
                              "Ran 5 tests in 1.2s: FAILED (failures=2)"),
            "vitest": (" Test Files  2 passed (2)\n      Tests  9 passed (9)\n", "Tests  9 passed (9)"),
            "jest": ("Tests:       1 failed, 6 passed, 7 total\n", "Tests:       1 failed, 6 passed, 7 total"),
            "mocha": ("  8 passing (12ms)\n", "8 passing (12ms)"),
            "cargo": ("test result: ok. 31 passed; 0 failed; 0 ignored\n",
                      "test result: ok. 31 passed; 0 failed; 0 ignored"),
            "bun": (" 6 pass\n 0 fail\n", "6 pass"),
            "playwright": ("Running 12 tests\n  12 passed (5.2s)\n", "12 passed (5.2s)"),
            "node test": ("# tests 4\n# pass 4\n# fail 0\n", "# pass 4"),
            "node test spec": (
                "\N{INFORMATION SOURCE} tests 1\n\N{INFORMATION SOURCE} pass 1\n\N{INFORMATION SOURCE} fail 0\n",
                "\N{INFORMATION SOURCE} pass 1"),
            "go": ("ok  \texample.com/a\t0.1s\nok  \texample.com/b\t0.2s\n", "go: 2 packages ok"),
        }
        for runner, (output, expected) in outputs.items():
            with self.subTest(runner=runner):
                found = test_run_output.runner_summaries(output)

                self.assertEqual(1, len(found), found)
                self.assertIn(expected, found[0])

    def test_a_failure_count_above_zero_is_kept_and_a_zero_count_is_not(self):
        outputs = {
            "mocha": ("  3 passing (9ms)\n  2 failing\n", "2 failing"),
            "bun": (" 3 pass\n 2 fail\n", "2 fail"),
            "node test": ("# tests 5\n# pass 3\n# fail 2\n", "# fail 2"),
            "playwright": ("  2 failed\n  3 passed (5.2s)\n", "2 failed"),
            "go": ("ok  \texample.com/a\t0.1s\nFAIL\texample.com/b\t0.2s\n", "FAIL\texample.com/b"),
        }
        for runner, (output, expected) in outputs.items():
            with self.subTest(runner=runner):
                found = test_run_output.runner_summaries(output)

                self.assertTrue(any(line.startswith(expected) for line in found), found)

        self.assertEqual(["3 pass"], test_run_output.runner_summaries(" 3 pass\n 0 fail\n"))
        self.assertEqual(["# pass 3"], test_run_output.runner_summaries("# pass 3\n# fail 0\n"))

    def test_a_chained_command_keeps_each_distinct_summary_in_order_and_at_most_five(self):
        cargo_lines = "".join(f"test result: ok. {count} passed; 0 failed\n" for count in range(1, 8))
        output = "Tests  9 passed (9)\n8 passing (1ms)\nTests  9 passed (9)\n" + cargo_lines

        found = test_run_output.runner_summaries(output)

        self.assertEqual(["Tests  9 passed (9)", "8 passing (1ms)"], found[:2])
        self.assertEqual(5, len(found))
        self.assertEqual(7, len(test_run_output.runner_summaries(cargo_lines, limit=None)))

    def test_a_printed_line_that_is_no_runner_summary_gives_no_summary(self):
        output = "496 tests registered\nlint ok\nok\nTotal: 496 passed checks\n"

        self.assertEqual([], test_run_output.runner_summaries(output))

    def test_blank_lines_before_a_summary_are_not_part_of_it(self):
        found = test_run_output.runner_summaries("foo\n\n  5 passing (20ms)\n")

        self.assertEqual(["5 passing (20ms)"], found)

    def test_a_summary_that_counts_no_passed_test_is_no_runner_summary(self):
        outputs = ("Ran 0 tests in 0.000s\n\nOK\n", "  0 passing (1ms)\n", "# pass 0\n", " 0 pass\n",
                   "test result: ok. 0 passed; 0 failed; 0 ignored\n", "  0 passed (1.2s)\n")
        for output in outputs:
            with self.subTest(output=output):
                self.assertEqual([], test_run_output.runner_summaries(output))
                self.assertEqual(0, test_run_output.passed_test_count(output))

    def test_a_cargo_failure_with_no_passed_test_is_still_a_summary(self):
        found = test_run_output.runner_summaries("test result: FAILED. 0 passed; 1 failed; 0 ignored\n")

        self.assertEqual(1, len(found))

    def test_only_go_package_lines_count_as_go_summaries(self):
        for output in ("ok 1 - adds\n", "echo ok done\nok done\n"):
            with self.subTest(output=output):
                self.assertEqual([], test_run_output.runner_summaries(output))
                self.assertEqual(0, test_run_output.passed_test_count(output))

        cached = "ok  \texample.com/a\t(cached)\n"
        self.assertEqual(["go: 1 packages ok"], test_run_output.runner_summaries(cached))

    def test_the_dotfiles_suite_total_is_the_summary_of_a_passing_run(self):
        total = "3679 tests in 95 files, wall-clock 428.1s, sum of per-file seconds 1400.6s, 0 failed"
        output = f"test_a.py    3 tests    0.1s OK\n\n{total}\n"

        self.assertEqual([total], test_run_output.runner_summaries(output))
        self.assertEqual([], test_run_output.runner_summaries(
            "0 tests in 0 files, wall-clock 0.0s, sum of per-file seconds 0.0s, 0 failed\n"))

    def test_the_dotfiles_suite_total_is_kept_when_it_counts_failed_files(self):
        total = "3679 tests in 95 files, wall-clock 428.1s, sum of per-file seconds 1400.6s, 2 failed"

        found = test_run_output.runner_summaries(f"test_a.py    3 tests    0.1s FAILED\n\n{total}\nFAILED: tests\n")

        self.assertEqual([total], found)


if __name__ == "__main__":
    unittest.main()
