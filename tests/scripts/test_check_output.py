"""Tests for check_output.py: which check failures are setup faults, and which lines name a failed test."""
import importlib.util
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
sys.path.insert(0, str(toolkit_paths.CODE_DIR))
import check_output
import check_scope
import code_step_gates
import code_step_verification
import criteria_verdict
import full_check
import script_utils
import test_run_output

CROSS = chr(0xD7)
PASS, NOT_PASS, NOT_RUN = "pass", "not pass", "not run"
NO_TESTS_RAN_FLAG = criteria_verdict.NO_TEST_MATCHED_FLAG
# (name, command, exit code, output, verdict, full_check result or None to skip it, coder_gate result). One row per
# kind of run that the pass rules once judged differently.
VERDICT_ROWS = [
    ("a pass", "pytest tests/", 0, "===== 3 passed in 0.10s =====", check_output.PASSED, full_check.PASSED,
     "pass"),
    ("a plain failure", "pytest tests/", 1, "FAILED tests/a.py::t - boom\n===== 1 failed, 2 passed in 0.1s =====",
     check_output.FAILED, None, "failed"),
    ("exit 0 with a failing summary", "npm test", 0, " Test Files  1 failed (1)\n      Tests  1 failed | 2 passed (3)",
     check_output.FAILED_EXIT_ZERO, full_check.FAILED_EXIT_ZERO, "failed"),
    ("a runner piped into a tail", "pytest tests/ | tail -5", 0, "1 failed, 2 passed in 0.1s",
     check_output.FAILED_EXIT_ZERO, full_check.FAILED_EXIT_ZERO, "failed"),
    ("a Django run of 0 tests", "python manage.py test app", 0,
     "Found 0 test(s).\nRan 0 tests in 0.000s\n\nNO TESTS RAN", check_output.NO_TESTS_RAN, full_check.UNVERIFIED,
     "setup-fault"),
    ("a filtered pytest run that matched no test", "pytest tests/ -k nothing", 0, "===== 42 deselected in 0.20s =====",
     check_output.NO_TESTS_RAN, full_check.UNVERIFIED, "failed"),
    ("a filtered vitest run that matched no test", "npx vitest run -t totals", 0,
     " Test Files  1 skipped (1)\n      Tests  7 skipped (7)", check_output.NO_TESTS_RAN, full_check.UNVERIFIED,
     "failed"),
    ("a filtered cargo run that matched no test", "cargo test fault_codes", 0,
     "test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 11 filtered out", check_output.NO_TESTS_RAN,
     full_check.UNVERIFIED, "failed"),
    ("a chained run where one runner ran no test", "python manage.py test app && pytest tests/", 0,
     "Ran 0 tests in 0.000s\n\nOK\n===== 3 passed in 0.10s =====", check_output.NO_TESTS_RAN, full_check.UNVERIFIED,
     "setup-fault"),
    ("a passing run that logs the phrase", "pytest tests/", 0, "no tests ran\n===== 3 passed in 0.10s =====",
     check_output.NO_TESTS_RAN, full_check.UNVERIFIED, "setup-fault"),
    ("jest with --passWithNoTests", "npx jest --passWithNoTests", 0, "No tests found, exiting with code 0",
     check_output.NO_TESTS_RAN, full_check.UNVERIFIED, "setup-fault"),
    ("jest with a zero-total summary", "npm test", 0, "Test Suites: 0 total\nTests:       0 total\n",
     check_output.NO_TESTS_RAN, full_check.UNVERIFIED, "setup-fault"),
    ("a non-test command that prints the phrase", "cat ci.log", 0, "no tests ran\n===== 3 passed in 0.10s =====",
     check_output.PASSED, full_check.PASSED, "pass"),
    ("a filtered run with a failing summary", "pytest tests/ -k totals", 0, "===== 1 failed in 0.10s =====",
     check_output.FAILED_EXIT_ZERO, full_check.FAILED_EXIT_ZERO, "failed"),
    ("a file print that holds a failing summary", "cat run.log", 0, "1 failed, 2 passed in 0.1s",
     check_output.FAILED_EXIT_ZERO, full_check.FAILED_EXIT_ZERO, "failed"),
    ("a script wrapper that swallowed a failing summary", "bash tests/run.sh", 0, "1 failed, 2 passed in 0.1s",
     check_output.FAILED_EXIT_ZERO, full_check.FAILED_EXIT_ZERO, "failed"),
    ("a negated runner that prints a failed summary and exits zero", "! pytest new_test.py", 0,
     "1 failed, 2 passed in 0.1s", check_output.FAILED_EXIT_ZERO, full_check.FAILED_EXIT_ZERO, "failed"),
    ("a negated filtered runner that prints a failed summary and exits zero", "! pytest t.py::test_new", 0,
     "1 failed in 0.10s", check_output.FAILED_EXIT_ZERO, full_check.FAILED_EXIT_ZERO, "failed"),
    ("a tail of a log that holds a failing summary", "tail -5 run.log", 0, "1 failed, 2 passed in 0.1s",
     check_output.FAILED_EXIT_ZERO, full_check.FAILED_EXIT_ZERO, "failed"),
    ("a tail with a line count of a log that holds a failing summary", "tail -n 50 run.log", 0,
     "1 failed, 2 passed in 0.1s", check_output.FAILED_EXIT_ZERO, full_check.FAILED_EXIT_ZERO, "failed"),
    ("a timeout", "pytest tests/", None, "", check_output.NOT_RUN, full_check.NOT_RUN_TIMEOUT, "timeout"),
]
COARSE_OUTCOME = {check_output.PASSED: PASS, check_output.FAILED: NOT_PASS, check_output.FAILED_EXIT_ZERO: NOT_PASS,
                  check_output.NO_TESTS_RAN: NOT_PASS, check_output.NOT_RUN: NOT_RUN}


def load_coder_gate():
    spec = importlib.util.spec_from_file_location("coder_gate_for_verdict", toolkit_paths.CODE_DIR / "coder_gate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

    def test_a_no_tests_line_is_a_setup_fault_only_when_it_is_the_reason_for_the_non_zero_exit(self):
        rows = [
            ("No tests found, exiting with code 0\nerror TS2322: type mismatch", False),
            ("No test files found, exiting with code 0\nerror TS2322: type mismatch", False),
            ("No tests found, exiting with code 1", True),
            ("No test files found, exiting with code 1", True),
            ("NO TESTS RAN", True),
            ("no tests ran in 0.01s", True),
        ]
        for output, is_fault in rows:
            with self.subTest(output=output):
                self.assertEqual(is_fault, check_output.is_setup_fault(1, output, self.repo))

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

    def test_failing_test_lines_name_each_cargo_and_nextest_failure_and_its_panic_line(self):
        output = "\n".join([
            "     Running tests/worker.rs (target/debug/deps/worker-1f2e)",
            "test worker_drains_the_queue ... ok",
            "       FAIL [  30.645s] (1890/1890) ledger::worker worker_exits_after_three_cache_busy_passes",
            "    test worker_exits_after_three_cache_busy_passes ... FAILED",
            "    thread 'worker_exits_after_three_cache_busy_passes' (2641884) panicked at tests/worker.rs:936:5:",
            "    assertion `left == right` failed: the worker kept running",
            "      left: 4",
            "     right: 3",
            "    note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace",
            "",
            "test result: FAILED. 1889 passed; 1 failed; 0 ignored",
        ])

        expected = [
            "FAIL [  30.645s] (1890/1890) ledger::worker worker_exits_after_three_cache_busy_passes",
            "test worker_exits_after_three_cache_busy_passes ... FAILED",
            "thread 'worker_exits_after_three_cache_busy_passes' (2641884) panicked at tests/worker.rs:936:5:",
        ]
        self.assertEqual(expected, check_output.failing_test_lines(output))

    def test_the_failing_test_quote_of_a_cargo_run_holds_each_panic_message(self):
        output = "\n".join([
            "running 2 tests",
            "test orders_total ... FAILED",
            "test orders_sort ... ok",
            "",
            "failures:",
            "",
            "---- orders_total stdout ----",
            "thread 'orders_total' (77) panicked at tests/orders.rs:9:5:",
            "expected 3, got 4",
            "note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace",
            "",
            "test result: FAILED. 1 passed; 1 failed; 0 ignored",
        ])

        quote = check_output.failing_test_quote(output, output[-40:])

        self.assertIn("test orders_total ... FAILED", quote)
        self.assertIn("thread 'orders_total' (77) panicked at tests/orders.rs:9:5:\nexpected 3, got 4", quote)

    def test_the_failing_test_quote_of_real_cargo_and_nextest_output_holds_the_assertion_values(self):
        fixtures = pathlib.Path(__file__).resolve().parent / "fixtures"
        expected_quotes = {
            "cargo_test_failed_assertion.txt": (
                "\nFailing tests:\nthread 'tests::x_total' (2268265) panicked at src/lib.rs:8:9:\n"
                "assertion `left == right` failed\n  left: 3\n right: 4\ntest tests::x_total ... FAILED"),
            "nextest_failed_assertion.txt": (
                "\nFailing tests:\nthread 'tests::x_total' (2268333) panicked at src/lib.rs:8:9:\n"
                "    assertion `left == right` failed\n      left: 3\n     right: 4\n"
                "FAIL [   0.004s] (3/3) crate tests::x_total\ntest tests::x_total ... FAILED"),
        }
        for name, expected_quote in expected_quotes.items():
            with self.subTest(name=name):
                output = (fixtures / name).read_text()

                quote = check_output.failing_test_quote(output, "TAIL FALLBACK")

                self.assertEqual(expected_quote, quote)
                self.assertNotIn("running 1 test", quote)
                self.assertNotIn("Cancelling due to test failure", quote)

    def test_a_panic_line_compares_equal_across_runs_whatever_its_thread_id_line_and_column(self):
        first_run = "thread 'worker_exits' (2641884) panicked at tests/worker.rs:936:5:"
        second_run = "thread 'worker_exits' (311) panicked at tests/worker.rs:951:9:"
        other_file = "thread 'worker_exits' (311) panicked at tests/queue.rs:936:5:"

        normalized = check_output.normalized_log_line(first_run)

        self.assertEqual(normalized, check_output.normalized_log_line(second_run))
        self.assertEqual("thread 'worker_exits' panicked at tests/worker.rs:", normalized)
        self.assertNotEqual(normalized, check_output.normalized_log_line(other_file))

    def test_a_panic_line_with_no_thread_id_is_a_failing_test_line_and_its_values_are_quoted(self):
        output = ("thread 'tests::x_total' panicked at src/lib.rs:8:9:\n"
                  "assertion `left == right` failed\n  left: 3\n right: 4")

        quote = check_output.failing_test_quote(output, "TAIL FALLBACK")

        self.assertEqual(["thread 'tests::x_total' panicked at src/lib.rs:8:9:"],
                         check_output.failing_test_lines(output))
        self.assertIn("left: 3", quote)
        self.assertNotIn("TAIL FALLBACK", quote)
        self.assertEqual("thread 'tests::x_total' panicked at src/lib.rs:",
                         check_output.normalized_log_line("thread 'tests::x_total' panicked at src/lib.rs:8:9:"))

    def test_a_bare_word_traceback_line_in_a_unittest_failure_is_kept(self):
        output = "\n".join([
            "FAIL: test_totals (orders.tests.OrderTest)",
            "Traceback (most recent call last):",
            '  File "orders/tests.py", line 9, in test_totals',
            "    raise",
            "AssertionError: 1 != 2",
        ])

        quoted = check_output.failing_test_errors(output)

        self.assertIn("    raise", quoted)

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


class CheckVerdictTest(unittest.TestCase):
    """check_verdict and the three pass rules that call it read every row the same way."""

    def test_a_negated_filtered_run_that_matched_no_test_passes_the_verdict_but_reads_red_for_a_criterion(self):
        # full_check reads no passed summary as unverified, so this row stays out of VERDICT_ROWS.
        command = "! pytest t.py -k nothing"
        output = "===== 42 deselected in 0.20s ====="

        self.assertEqual(check_output.PASSED, check_output.check_verdict(command, 0, output))
        self.assertEqual("RED", criteria_verdict.judge_item(command, f"`{command}` exits 0", 0, output).outcome)

    def test_a_search_that_names_a_runner_is_not_read_for_no_tests_ran(self):
        # criteria_verdict bans an exit-0 search, so this command stays out of VERDICT_ROWS.
        verdict = check_output.check_verdict("rg -t py pytest scripts/", 0, "no tests ran")

        self.assertEqual(check_output.PASSED, verdict)

    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.repo = pathlib.Path(scratch.name)
        self.log = self.repo / "check.log"
        self.coder_gate = load_coder_gate()

    def full_check_outcome(self, command, code, output):
        def fake_check_command(_repo, _command, log, _timeout, _env, _on_start):
            pathlib.Path(log).write_text(output)
            return code

        with mock.patch.object(full_check, "run_check_command", fake_check_command):
            result, _tail, _details = full_check.run(self.repo, command, self.log, 60, receipt=False)

        if result == full_check.PASSED:
            return PASS, result
        if result == full_check.NOT_RUN_TIMEOUT:
            return NOT_RUN, result
        return NOT_PASS, result

    def coder_gate_outcome(self, command, code, output):
        with mock.patch.object(script_utils, "run_process", return_value=(code, output, "")):
            failures, _skipped, timed_out, _not_started = self.coder_gate.run_commands(
                {"repoRoot": str(self.repo), "commands": [command]})

        with mock.patch.object(self.coder_gate, "changed_files", return_value=[]):
            real_failures, setup_faults, command_errors = self.coder_gate.sort_failures(failures, str(self.repo))

        gate_result = self.coder_gate.gate_outcome(real_failures, command_errors, setup_faults, timed_out)
        if timed_out:
            return NOT_RUN, gate_result, failures
        return (NOT_PASS if failures else PASS), gate_result, failures

    def criteria_outcome(self, command, code, output):
        verdict = criteria_verdict.judge_item(command, f"`{command}` exits 0", code, output)
        return (PASS if verdict.outcome == "GREEN" else NOT_PASS), verdict

    def test_check_verdict_and_every_pass_rule_agree_on_each_command_and_output(self):
        for name, command, code, output, verdict, full_check_result, gate_result in VERDICT_ROWS:
            with self.subTest(name):
                expected = COARSE_OUTCOME[verdict]

                self.assertEqual(verdict, check_output.check_verdict(command, code, output))
                full_check_outcome, result = self.full_check_outcome(command, code, output)
                self.assertEqual(expected, full_check_outcome)
                if full_check_result is not None:
                    self.assertEqual(full_check_result, result)
                gate_coarse, gate_actual, gate_failures = self.coder_gate_outcome(command, code, output)
                self.assertEqual(expected, gate_coarse)
                self.assertEqual(gate_result, gate_actual)
                if verdict == check_output.FAILED_EXIT_ZERO:
                    self.assertIn(check_output.SUMMARY_FAILURE_NOTE, gate_failures[0][2])
                    self.assertIn(check_output.SUMMARY_FAILURE_NOTE, self.coder_gate.denial(gate_failures))
                if verdict == check_output.NO_TESTS_RAN:
                    self.assertIn(check_output.NO_TEST_MATCHED_NOTE, gate_failures[0][2])
                    self.assertIn(check_output.NO_TEST_MATCHED_NOTE, self.coder_gate.denial(gate_failures))
                # A timeout reaches the plan-criteria rule as exit code 124, never as None.
                if code is None:
                    continue

                criteria_result, item = self.criteria_outcome(command, code, output)
                self.assertEqual(expected, criteria_result)
                if verdict == check_output.NO_TESTS_RAN:
                    self.assertEqual(NO_TESTS_RAN_FLAG, item.flag)
                    self.assertIn(criteria_verdict.NO_TEST_MATCHED_NOTE, item.output)
                if verdict == check_output.FAILED_EXIT_ZERO:
                    self.assertIsNone(item.flag)
                    self.assertIn(criteria_verdict.SUMMARY_FAILURE_NOTE, item.output)


# (command, runs tests, runner families, is a check, command_check_scope). One row per kind of command the former
# deciders judged by their own tables.
COMMAND_ROWS = [
    ("pytest", True, {"python"}, True, "whole"),
    ("vitest", True, {"js"}, True, "whole"),
    ("jest", True, {"js"}, True, "whole"),
    ("npm test", True, {"js"}, True, "whole"),
    ("npm run lint", False, set(), True, "whole"),
    ("cargo test", True, {"cargo"}, True, "none"),
    ("cargo test -p x", True, {"cargo"}, True, "targeted"),
    ("cargo nextest run", True, {"cargo"}, True, "none"),
    ("go test ./...", True, set(), True, "none"),
    ("manage.py test app", True, {"python"}, True, "targeted"),
    ("ruff check", False, set(), True, "whole"),
    ("tsc", False, set(), True, "none"),
    ("bash tests/run.sh", False, set(), False, "none"),
    ("cat run.log", False, set(), False, "none"),
    ("! pytest x", True, {"python"}, True, "targeted"),
    ("cd a && pytest b.py", True, {"python"}, True, "targeted"),
    ("npm test && git diff", True, {"js"}, True, "whole"),
    ("mocha", True, {"js"}, True, "none"),
    ("npx mocha", True, {"js"}, True, "none"),
    ("make test-unit", True, set(), True, "unresolved"),
    ("make -C x test", True, set(), True, "unresolved"),
    ("just test", True, set(), True, "none"),
    ("deno test", True, set(), True, "none"),
    ("pnpm --filter api test", True, {"js"}, True, "none"),
]


class CommandClassificationTest(unittest.TestCase):
    """check_scope answers every command question once; each former decider reads its answer."""

    def setUp(self):
        temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temp_directory.cleanup)
        self.repo = pathlib.Path(temp_directory.name)

    def ran_and_skipped_commands(self, command, configured, run_whole_suites=False):
        # What run_verification_commands does with a listed command when no one asked for the configured check to
        # run and the repo's configured quality check is `configured`.
        run_result = mock.Mock(return_value=(0, ""))
        verdict = mock.Mock(code=0, output="", hits=None)
        with mock.patch.object(code_step_verification, "verification_command", return_value=command), \
                mock.patch.object(code_step_verification.plan_format, "automated_verification_rows",
                                  return_value=[(0, "- [ ] **Check**: `x`")]), \
                mock.patch.object(code_step_verification, "run_command", run_result), \
                mock.patch.object(full_check, "configured_check_command", return_value=configured), \
                mock.patch.object(code_step_verification.full_check_receipt, "valid_receipt",
                                  return_value={"result": full_check.PASSED}), \
                mock.patch.object(code_step_verification, "item_verdict", return_value=verdict):
            results, skipped, _unparsed = code_step_verification.run_verification_commands(
                self.repo, "section", run_whole_suites=run_whole_suites)
        ran_commands = [result[0] for result in results]
        return ran_commands, skipped

    def test_only_the_configured_check_is_skipped_and_run_whole_suites_runs_it(self):
        configured = "npm test && npm run lint"
        for command in ("npm run test:e2e", "npm run lint:fix", "npm run build && node x.js"):
            with self.subTest(runs=command):
                ran_commands, skipped = self.ran_and_skipped_commands(command, configured)
                self.assertEqual([command], ran_commands)
                self.assertEqual([], skipped)
        for command in ("npm test", "npm run lint", configured):
            with self.subTest(skipped=command):
                ran_commands, skipped = self.ran_and_skipped_commands(command, configured)
                self.assertEqual([], ran_commands)
                self.assertEqual([command], skipped)
                ran_commands, skipped = self.ran_and_skipped_commands(command, configured, run_whole_suites=True)
                self.assertEqual([command], ran_commands)
                self.assertEqual([], skipped)

    def test_each_command_gets_one_answer_from_check_scope_and_every_former_decider_agrees(self):
        for command, runs_tests, families, is_check, scope in COMMAND_ROWS:
            with self.subTest(command=command):
                self.assertEqual(runs_tests, check_scope.runs_tests(command))
                self.assertEqual(families, check_scope.runner_family(command))
                self.assertEqual(is_check, check_scope.is_check(command))
                self.assertEqual(scope, check_scope.command_check_scope(command, self.repo))

                runs_whole = scope == "whole"
                self.assertEqual(runs_whole, check_scope.runs_whole_check(command, self.repo))
                self.assertEqual(runs_tests and not runs_whole,
                                 code_step_gates.takes_listed_test_command(command, self.repo))
                self.assertEqual(families or {code_step_gates.UNKNOWN_FAMILY},
                                 code_step_gates.test_command_families(command))
                self.assertEqual(command != "cat run.log" and command != "! pytest x",
                                 check_output.prints_own_runner_summary(command))

    def test_only_a_command_with_a_test_runner_step_runs_tests(self):
        not_runs = ("git grep -n test -- src", "ruff check tests/", "test -f out.txt", "npm run lint",
                    "cd tests && ls", "ruff check test", "npx eslint test", "mypy test-utils", "npm install test-x",
                    "npm i test-utils", "pnpm add test-helpers", "npm -D install test-x")
        runs = ("npm run test:unit", "go test ./pkg/...", "FOO=1 vitest run a.test.ts", "npx mocha a.js",
                "npm run typecheck && npm test", "cd pkg && npm test", "(cd pkg && pytest)", "a&&pytest",
                "pipenv run python backend/manage.py test app.tests", "make test-consistency ARGS=a.test.ts",
                "pnpm --filter api test", "make install test", "make update test", "just install test",
                "pnpm --filter add test", "python -m unittest tests.test_a", "uv run python3 -m unittest discover",
                "nice -n 19 env CARGO_BUILD_JOBS=4 cargo nextest run --lib -E 'test(widget_sorts)'")
        for command in not_runs + runs:
            with self.subTest(command=command):
                self.assertEqual(command in runs, check_scope.runs_tests(command))

    def test_only_a_command_with_a_step_that_can_print_a_summary_prints_its_own(self):
        quotes = ("cat a.log", "cd tests && ls", "! pytest x", "FOO=1 cat a.log", "tail -5 run.log",
                  "head run.log", "sed -n 1p run.log", "cat run.log | tail",
                  "less run.log", "sort run.log | uniq", "awk 1 run.log", "wc -l run.log")
        prints = ("bash tests/run.sh", "cd pkg && bash tests/run.sh", "cat a.log; pytest", 'cat "a',
                  "pytest x | tail -5")
        for command in quotes + prints:
            with self.subTest(command=command):
                self.assertEqual(command in prints, check_scope.prints_own_runner_summary(command))

    def test_the_output_reader_asks_check_scope_whether_a_filtered_run_names_tests(self):
        no_pass_output = "test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 11 filtered out"
        filtered = ("cargo test fault_codes", "cargo test -- fault_codes", "cargo +nightly test fault_codes",
                    "pytest -k fault", "make test -k fault", "cargo test --skip foo")
        whole = ("cargo test", "cargo test -p core", "cargo test --lib", "cargo test --features a --color always",
                 "pytest", "cargo test --retries 2", 'echo "cargo test x"', "cargo test --",
                 "cargo test 2>&1", "cargo test > log", "cargo test --lib 2>&1", "cargo test -E x")
        for command in filtered:
            with self.subTest(filtered=command):
                self.assertTrue(check_scope.names_test_filter(command))
                self.assertTrue(test_run_output.matches_no_test(command, 0, no_pass_output))
        for command in whole:
            with self.subTest(whole=command):
                self.assertFalse(check_scope.names_test_filter(command))
                self.assertFalse(test_run_output.matches_no_test(command, 0, no_pass_output))

    def test_the_value_of_each_cargo_flag_is_no_test_filter(self):
        no_pass_output = "test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 11 filtered out"
        flag_commands = {"-A": "cargo test -A warnings", "-W": "cargo test -W unused",
                         "-D": "cargo test -D warnings", "--retries": "cargo test --retries 2",
                         "--test-threads": "cargo test --test-threads 4"}
        for flag, command in flag_commands.items():
            with self.subTest(flag=flag):
                self.assertFalse(check_scope.names_test_filter(command))
                self.assertFalse(test_run_output.matches_no_test(command, 0, no_pass_output))

    def test_a_cargo_test_in_a_quoted_string_of_another_step_runs_no_test(self):
        command = 'echo "cargo test x"'

        self.assertFalse(check_scope.runs_tests(command))
        self.assertEqual("none", check_scope.command_check_scope(command, self.repo))
        self.assertFalse(check_scope.runs_whole_check(command, self.repo))
        self.assertFalse(check_scope.names_test_filter(command))

    def test_a_check_is_any_test_lint_typecheck_or_build_run_through_its_wrappers(self):
        checks = ("python3 -m pytest", "uv run pytest", "time npx vitest run", "env A=1 cargo +nightly clippy",
                  "cargo nextest run", "bundle exec rspec", "pnpm exec jest", "npm run test:unit", "yarn lint",
                  "make typecheck", "go vet ./...", "./node_modules/.bin/jest", "ruff format --check",
                  "bats", "bats tests/a.bats", "pyright", "pyright src", "mocha", "just test", 'pytest "a',
                  "yarn jest", "pnpm vitest", "docker exec c pytest", "npm exec jest", "bun x vitest", "vim pytest",
                  "python -c jest",
                  "yarn test list", "bun test add", "pnpm test update", "npm test list", "npm test update",
                  "bun test list", "pnpm test add", "yarn test info")
        not_checks = ("git status", "cargo fmt", "npm install", "make deploy", "cargo build", "ls tests",
                      "npm install jest", "npm i -D vitest", "pip install pytest", "uv add pytest", "which pytest",
                      "python -m pip install pytest", "python3 -m pip show pytest", "uv pip install pytest",
                      "cargo install nextest", "npm i test-utils",
                      "npm install -D jest", "command -v pytest", "pip show pytest", "pip3 install pytest",
                      "yarn add test-utils", "pnpm add test-helpers", "npm uninstall test-x", "cargo add nextest",
                      "npm ls jest", "npm ci jest", "pipx install pytest", "pip download pytest",
                      "brew install jest", "apt install pytest",
                      "pnpm --filter api add jest", "npm --prefix x install jest", "pnpm -w add jest",
                      "npm -w api install jest", "npm -D install test-x",
                      "pnpm -F api add jest", "pnpm --dir x add jest", "apt-get install pytest",
                      "dnf install pytest", "yum install pytest", "apk add pytest", "npm upgrade jest",
                      "npm search jest", "yarn upgrade test-x", "npm up jest", "npm un jest", "npm why jest",
                      "npm outdated jest", "yarn global add jest", "yarn workspace api add jest")
        for command in checks:
            with self.subTest(check=command):
                self.assertTrue(check_scope.is_check(command))
        for command in not_checks:
            with self.subTest(not_check=command):
                self.assertFalse(check_scope.is_check(command))

    def test_a_cargo_test_names_a_target_only_by_a_test_target_or_a_name(self):
        named = ("cargo test --lib", "cargo test --doc", "cargo test --test integration", "cargo test --bin=app",
                 "cargo test --example demo", "cargo test --bench parse", "cargo test empty_input",
                 "cargo test --release --features a empty_input", "cargo +nightly test empty_input",
                 "cargo test -p core empty_input")
        full = ("cargo test", "cargo test -p core", "cargo test --package=core", "cargo test --workspace",
                "cargo test --all-targets empty_input", "cargo test --workspace --lib", "cargo test --tests",
                "cargo test --exclude x", "cargo test -- empty_input", "cargo test -- --ignored",
                "cargo test --features a --color always", "cargo test --retries 2", "cargo test --test-threads 4",
                "cargo nextest run empty_input", "pytest tests/a.py")
        for command in named:
            with self.subTest(named=command):
                self.assertTrue(check_scope.names_cargo_test_target(command))
        for command in full:
            with self.subTest(full=command):
                self.assertFalse(check_scope.names_cargo_test_target(command))
