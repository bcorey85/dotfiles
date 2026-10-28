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

    def test_a_cargo_test_name_after_option_flags_is_a_filter(self):
        commands = [
            "cargo test --test billing totals",
            "cargo test -p ledger --test billing totals",
            "cargo test --test billing -- totals",
            "cargo test --release --lib totals",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.assertTrue(test_run_output.matches_no_test(command, 0, NO_TEST_OUTPUTS["cargo"]))

    def test_a_cargo_test_with_only_options_is_not_a_filter(self):
        commands = ["cargo test --test billing", "cargo test -p ledger --test billing --release", "cargo test"]
        for command in commands:
            with self.subTest(command=command):
                self.assertFalse(test_run_output.matches_no_test(command, 0, NO_TEST_OUTPUTS["cargo"]))

    def test_a_check_that_only_names_a_test_does_not_run_tests(self):
        for command in ("git grep -n test -- src", "ruff check tests/", "test -f out.txt", "npm run lint",
                        "cd tests && ls", "ruff check test", "npx eslint test", "mypy test-utils"):
            with self.subTest(command=command):
                self.assertFalse(test_run_output.runs_tests(command))

    def test_a_step_of_a_command_that_runs_tests_is_a_test_run(self):
        for command in ("npm run test:unit", "go test ./pkg/...", "FOO=1 vitest run a.test.ts", "npx mocha a.js",
                        "npm run typecheck && npm test", "cd pkg && npm test", "(cd pkg && pytest)", "a&&pytest",
                        "pipenv run python backend/manage.py test app.tests", "make test-consistency ARGS=a.test.ts",
                        "pnpm --filter api test"):
            with self.subTest(command=command):
                self.assertTrue(test_run_output.runs_tests(command))


if __name__ == "__main__":
    unittest.main()
