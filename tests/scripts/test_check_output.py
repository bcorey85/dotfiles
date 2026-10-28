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

    def test_a_tail_that_holds_the_failing_tests_is_left_as_it_is(self):
        output = "noise\nFAIL: test_x (app.tests.T)\n"

        self.assertEqual(output, check_output.tail_with_failing_tests(output, output))
