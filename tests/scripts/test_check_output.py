"""Tests for check_output.py: which check failures are setup faults, and which lines name a failed test."""
import pathlib
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import check_output

CROSS = chr(0xD7)


class CheckOutputTest(unittest.TestCase):
    def setUp(self):
        temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temp_directory.cleanup)
        self.repo = pathlib.Path(temp_directory.name)

    def test_failing_test_errors_are_bounded_per_test(self):
        output = "\n".join(["FAILED a - boom"] + [f"  a detail {n}" for n in range(10)]
                           + ["FAILED b - bang", "  b detail"])
        quoted = check_output.failing_test_errors(output, lines_per_test=2)
        self.assertEqual(["FAILED a - boom", "  a detail 0", "  a detail 9", "FAILED b - bang", "  b detail"], quoted)
        self.assertEqual([], check_output.failing_test_errors("FAILED a - boom"))

    def test_a_jest_file_with_several_failing_tests_keeps_the_error_of_each(self):
        output = "\n".join([
            "FAIL src/a.test.js",
            "  ● totals › adds",
            "",
            "    expect(received).toBe(expected)",
            "    Expected: 2",
            "    Received: 1",
            "    at a.test.js:5:3",
            "    at b.js:1:1",
            "    at c.js:1:1",
            "",
            "  ● totals › subtracts",
            "",
            "    expect(received).toBe(expected)",
            "    Expected: 3",
            "    Received: 4",
            "",
            "Test Suites: 1 failed, 1 total",
        ])

        quote = check_output.failing_test_quote(output, output[-400:])

        self.assertIn("    Expected: 2\n    Received: 1", quote)
        self.assertIn("    Expected: 3\n    Received: 4", quote)
        self.assertIn("● totals › adds", quote)
        self.assertIn("● totals › subtracts", quote)

    def test_failing_test_errors_skip_the_runner_summary_and_pass_lines(self):
        pytest_output = "\n".join([
            "E   assert 1 == 2", "=== short test summary info ===",
            "FAILED t.py::test_a - assert 1 == 2", "FAILED t.py::test_b - assert 3 == 4",
            "=== 2 failed in 0.1s ==="])
        self.assertEqual([], check_output.failing_test_errors(pytest_output))

        jest_output = "\n".join([
            "FAIL a.test.js", "PASS b.test.js", "  expected 1", "Test Suites: 1 failed, 1 passed, 2 total"])
        self.assertEqual(["FAIL a.test.js", "  expected 1"], check_output.failing_test_errors(jest_output))

    def test_failing_test_errors_parse_vitest_output(self):
        output = "\n".join([
            "FAIL  a.test.ts > totals", "AssertionError: expected 1 to be 2", " ❯ a.test.ts:5:3",
            "Test Files  1 failed (1)"])
        self.assertEqual(["FAIL  a.test.ts > totals", "AssertionError: expected 1 to be 2",
                          " ❯ a.test.ts:5:3"], check_output.failing_test_errors(output))

    def test_failing_test_errors_cut_each_line_at_the_character_limit(self):
        output = "FAILED a - boom\n" + "y" * 1000
        quoted = check_output.failing_test_errors(output)
        self.assertEqual(check_output.MAX_ERROR_LINE_CHARS, len(quoted[1]))

    def test_a_runner_that_cannot_start_the_program_is_a_setup_fault(self):
        outputs = {
            "uv": "error: Failed to spawn: `pytest`\n  Caused by: No such file or directory (os error 2)",
            "poetry": "Command not found: pytest",
            "pipenv": "Error: the command pytest could not be found within PATH or Pipfile's [scripts].",
        }
        for case, output in outputs.items():
            with self.subTest(case=case):
                self.assertTrue(check_output.is_setup_fault(2, output, self.repo))

    def test_a_missing_package_manifest_is_a_setup_fault(self):
        outputs = {
            "pnpm": "ERR_PNPM_NO_IMPORTER_MANIFEST_FOUND  No package.json (or package.yaml) was found in /repo.",
            "npm": "npm error enoent Could not read package.json: Error: ENOENT: no such file or directory, "
                   "open '/repo/package.json'",
            "yarn": "error Couldn't find a package.json file in \"/repo\"",
        }
        for case, output in outputs.items():
            with self.subTest(case=case):
                self.assertTrue(check_output.is_setup_fault(1, output, self.repo))

    def test_a_package_manager_version_mismatch_is_a_setup_fault_with_or_without_missing_modules(self):
        outputs = {
            "pnpm pm": "ERR_PNPM_BAD_PM_VERSION  This project is configured to use v9 of pnpm. Your v8 is installed",
            "pnpm engine": "ERR_PNPM_UNSUPPORTED_ENGINE  Unsupported environment (bad pnpm and/or Node.js version)",
            "npm ERR!": "npm ERR! code EBADENGINE\nnpm ERR! engine Unsupported engine",
            "npm error": "npm error code EBADENGINE\nnpm error engine Unsupported engine",
            "corepack": "Usage Error: This project is configured to use yarn@4.1.0 because of packageManager",
            "yarn": "error eslint@9: The engine \"node\" is incompatible with this module. Expected version \">=20\".",
        }
        for case, output in outputs.items():
            for include_missing_modules in (True, False):
                with self.subTest(case=case, include_missing_modules=include_missing_modules):
                    self.assertTrue(check_output.is_setup_fault(
                        1, output, self.repo, include_missing_modules=include_missing_modules))

    def test_a_run_that_found_no_test_is_a_setup_fault_unless_a_test_failed(self):
        self.assertTrue(check_output.is_setup_fault(5, "collected 0 items", self.repo))
        self.assertFalse(check_output.is_setup_fault(
            1, "No tests found, exiting with code 1\nFAIL: test_x (app.tests.T)", self.repo))
        self.assertFalse(check_output.is_setup_fault(1, "ImproperlyConfigured: settings are not configured", self.repo))

    def test_a_passing_run_with_no_tests_beside_a_real_failure_is_not_a_setup_fault(self):
        for line in ("No tests found, exiting with code 0", "No test files found, exiting with code 0"):
            with self.subTest(line=line):
                self.assertFalse(check_output.is_setup_fault(1, f"{line}\nerror TS2322: type mismatch", self.repo))

    def test_a_run_that_exits_non_zero_for_finding_no_test_is_a_setup_fault(self):
        for line in ("No tests found, exiting with code 1", "No test files found, exiting with code 1", "NO TESTS RAN",
                     "no tests ran in 0.01s"):
            with self.subTest(line=line):
                self.assertTrue(check_output.is_setup_fault(1, line, self.repo))

    def test_a_failed_test_that_names_a_missing_package_json_is_not_a_setup_fault(self):
        output = "Tests: 3 failed\nENOENT: no such file or directory, open '/tmp/fixture/package.json'"
        self.assertFalse(check_output.is_setup_fault(1, output, self.repo))

    def test_a_collection_error_that_names_a_module_from_outside_the_repo_is_a_setup_fault(self):
        output = "ERROR collecting tests/test_a.py\nModuleNotFoundError: No module named 'requests'"
        self.assertTrue(check_output.is_setup_fault(2, output, self.repo))

    def test_a_missing_module_named_after_a_subfolder_package_is_a_setup_fault(self):
        (self.repo / "backend/app").mkdir(parents=True)
        output = "ERROR collecting tests/test_a.py\nModuleNotFoundError: No module named 'app'"
        self.assertTrue(check_output.is_setup_fault(2, output, self.repo))

    def test_failing_test_lines_cover_pytest_unittest_vitest_and_jest_and_repeat_nothing(self):
        output = "\n".join([
            "FAILED tests/test_a.py::test_one - assert 1 == 2",
            "ERROR tests/test_b.py - ImportError",
            "FAIL: test_x (app.tests.T)",
            "ERROR: test_y (app.tests.T)",
            " FAIL  src/a.test.ts > suite > case",
            f"   {CROSS} case 2",
            "FAILED tests/test_a.py::test_one - assert 1 == 2",
            "plain line",
        ])

        expected = ["FAILED tests/test_a.py::test_one - assert 1 == 2", "ERROR tests/test_b.py - ImportError",
                    "FAIL: test_x (app.tests.T)", "ERROR: test_y (app.tests.T)",
                    "FAIL  src/a.test.ts > suite > case", f"{CROSS} case 2"]
        self.assertEqual(expected, check_output.failing_test_lines(output))

    def test_the_failing_test_lines_are_capped_and_sit_above_a_tail_that_lacks_them(self):
        output = "\n".join(f"FAILED tests/test_a.py::test_{number}" for number in range(30)) + "\n" + "x\n" * 50
        tail = "x\n" * 5

        report = check_output.tail_with_failing_tests(output, tail)

        self.assertTrue(report.startswith("Failing tests:\nFAILED tests/test_a.py::test_0\n"))
        self.assertEqual(20, report.count("FAILED "))
        self.assertTrue(report.endswith(tail))

    def test_the_error_text_of_a_vitest_failure_leaves_out_clock_passing_and_rule_lines(self):
        output = "\n".join([
            " ✓ src/a.test.ts > passes (2ms)",
            " FAIL  src/a.test.ts > suite > case",
            "AssertionError: expected 1 to be 2",
            " ✓ src/b.test.ts > also passes",
            "⎯⎯⎯⎯⎯⎯⎯⎯",
            "⎯⎯⎯⎯⎯⎯⎯ Failed Tests 2 ⎯⎯⎯⎯⎯⎯⎯",
            "⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/2]⎯",
            "   Duration  1.23s (transform 10ms, tests 5ms)",
            "   Start at  10:20:30",
        ])

        self.assertEqual(["FAIL  src/a.test.ts > suite > case", "AssertionError: expected 1 to be 2"],
                         check_output.failing_test_errors(output))

    def test_unittest_final_result_line_is_not_a_failing_test_and_the_quote_holds_the_error(self):
        output = "\n".join([
            "FAIL: test_totals (orders.tests.OrderTest)",
            "-" * 70,
            "Traceback (most recent call last):",
            '  File "orders/tests.py", line 9, in test_totals',
            "    self.assertEqual(1, 2)",
            "AssertionError: 1 != 2",
            "",
            "Ran 2 tests in 0.001s",
            "",
            "FAILED (failures=1)",
        ])

        quote = check_output.failing_test_quote(output, output[-400:])

        self.assertEqual(["FAIL: test_totals (orders.tests.OrderTest)"], check_output.failing_test_lines(output))
        self.assertIn("AssertionError: 1 != 2", quote)
        self.assertNotIn("FAILED (failures=1)", quote)
        self.assertNotIn("Ran 2 tests", quote)
        self.assertTrue(quote.startswith("\nFailing tests:\nFAIL: test_totals"), quote)

    def test_the_django_run_footer_does_not_take_the_lines_kept_after_a_long_traceback(self):
        output = "\n".join([
            "FAIL: test_totals (orders.tests.OrderTest)",
            "Traceback (most recent call last):",
            '  File "orders/tests.py", line 9, in test_totals',
            "    self.first()",
            '  File "orders/tests.py", line 5, in first',
            "    self.second()",
            '  File "orders/tests.py", line 3, in second',
            "    self.third()",
            '  File "orders/tests.py", line 1, in third',
            "    self.assertEqual(1, 2)",
            "AssertionError: 1 != 2",
            "",
            "-" * 70,
            "Ran 2 tests in 0.001s",
            "",
            "FAILED (failures=1)",
            "Destroying test database for alias 'default'...",
        ])

        quoted = check_output.failing_test_errors(output)

        self.assertEqual("AssertionError: 1 != 2", quoted[-1])

    def test_a_unittest_rule_line_does_not_take_one_of_the_error_lines(self):
        output = "\n".join([
            "FAIL: test_totals (orders.tests.OrderTest)",
            "-" * 70,
            "Traceback (most recent call last):",
            '  File "orders/tests.py", line 9, in test_totals',
            "    self.helper()",
            '  File "orders/tests.py", line 5, in helper',
            "    self.assertEqual(1, 2)",
            "AssertionError: 1 != 2",
        ])

        quoted = check_output.failing_test_errors(output)

        self.assertIn("AssertionError: 1 != 2", quoted)
        self.assertNotIn("-" * 70, quoted)

    def test_a_long_traceback_keeps_its_first_line_and_its_final_error_message(self):
        output = "\n".join([
            "FAIL: test_totals (orders.tests.OrderTest)",
            "Traceback (most recent call last):",
            '  File "orders/tests.py", line 9, in test_totals',
            "    self.first()",
            '  File "orders/tests.py", line 5, in first',
            "    self.second()",
            '  File "orders/tests.py", line 3, in second',
            "    self.third()",
            '  File "orders/tests.py", line 1, in third',
            "    self.assertEqual(1, 2)",
            "AssertionError: 1 != 2",
        ])

        quoted = check_output.failing_test_errors(output)

        self.assertEqual("FAIL: test_totals (orders.tests.OrderTest)", quoted[0])
        self.assertEqual("Traceback (most recent call last):", quoted[1])
        self.assertEqual("AssertionError: 1 != 2", quoted[-1])
        self.assertEqual(check_output.MAX_ERROR_LINES_PER_TEST + 1, len(quoted))

    def test_the_total_cap_does_not_send_the_quote_to_the_tail_when_a_later_test_is_cut(self):
        blocks = [[f"FAILED t.py::test_{n}"] + [f"  test {n} error {k}" for k in range(7)] for n in range(8)]
        output = "\n".join(line for block in blocks for line in block)

        quote = check_output.failing_test_quote(output, "TAIL FALLBACK")

        self.assertNotIn("TAIL FALLBACK", quote)
        for n in range(8):
            with self.subTest(n=n):
                self.assertIn(f"FAILED t.py::test_{n}", quote)
        cut_test_names = 2
        self.assertEqual(check_output.MAX_ERROR_LINES_TOTAL + cut_test_names, len(quote.splitlines()) - 2)

    def test_a_tail_that_holds_the_failing_tests_is_left_as_it_is(self):
        output = "noise\nFAIL: test_x (app.tests.T)\n"

        self.assertEqual(output, check_output.tail_with_failing_tests(output, output))

    def test_a_log_line_compares_equal_across_runs_only_when_its_failure_counts_match(self):
        cases = {
            "a pytest banner whose timing and passed count change":
                ("=== 1 failed, 10 passed in 1.23s ===", "=== 1 failed, 12 passed in 4.56s ===", True),
            "an error count that changes":
                ("1 failed, 1 error", "1 failed, 0 errors", False),
            "a message whose passed count changes":
                ("expected 3 passed", "expected 5 passed", False),
            "a message whose passed count does not change":
                ("expected 3 passed", "expected 3 passed", True),
            "a jest run time that changes":
                ("Time:        1.2 s", "Time:        1.5 s", True),
            "a vitest duration and start time that change":
                ("Duration  1.23s (transform 10ms, setup 0ms)", "Duration  1.56s (transform 12ms, setup 1ms)", True),
            "a vitest start time that changes":
                ("Start at  10:20:30", "Start at  10:21:45", True),
            "a jest time label whose number is an assertion value":
                ("Time: 5 expected", "Time: 6 expected", False),
            "a jest time label followed by an assertion about milliseconds":
                ("Time: 5 ms expected 3 ms", "Time: 5 ms expected 4 ms", False),
            "a jest time label followed by a limit":
                ("Time: 2 s, limit 1 s", "Time: 3 s, limit 1 s", False),
        }
        for name, (first_line, second_line, expected_equal) in cases.items():
            with self.subTest(name):
                first_normalized = check_output.normalized_log_line(first_line)
                second_normalized = check_output.normalized_log_line(second_line)

                self.assertEqual(expected_equal, first_normalized == second_normalized)

    def test_a_failing_block_runs_across_blank_lines_to_the_next_failing_line(self):
        cases = {
            "a jest file's second test after a blank line": (
                ["FAIL src/a.test.js", "  ● suite > old", "", "    Expected: 3", "", "  ● suite > new", "",
                 "    Expected: 5"],
                {"● suite > old", "Expected: 3", "● suite > new", "Expected: 5"}),
            "lines before the first failing line are not details": (
                ["noise", "FAIL: test_a", "    detail"], {"detail"}),
            "a blank line alone adds no detail": (["FAIL: test_a", ""], set()),
            "a jest PASS line after a failing block is not a detail": (
                ["FAIL src/a.test.js", "  ● suite > old", "", "PASS src/b.test.js", "Time:        1.2 s"],
                {"● suite > old", "Time:"}),
        }
        for name, (log_lines, expected_details) in cases.items():
            with self.subTest(name):
                self.assertEqual(expected_details, check_output.failing_block_details(log_lines))
