import importlib.util
import unittest

import toolkit_paths

module_spec = importlib.util.spec_from_file_location("source_paths", toolkit_paths.LIB_DIR / "source_paths.py")
source_paths = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(source_paths)


class IsCountedSourceTest(unittest.TestCase):
    def test_source_counts_and_tests_lockfiles_and_generated_files_do_not(self):
        cases = {
            "backend/src/orders.ts": True,
            "main.py": True,
            "backend/tests/orders.ts": False,
            "web/orders.spec.ts": False,
            "backend/test_orders.py": False,
            "app/tests.py": False,
            "package-lock.json": False,
            "web/yarn.lock": False,
            "web/__snapshots__/a.snap": False,
            "src/generated/api.ts": False,
            "web/dist/bundle.js": False,
            "web/app.min.js": False,
        }

        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(expected, source_paths.is_counted_source(path))


class IsRunnableTestFileTest(unittest.TestCase):
    def test_only_files_a_test_runner_can_target_count_and_test_support_files_do_not(self):
        cases = {
            "app/test_models.py": True,
            "app/orders_test.py": True,
            "web/orders.spec.ts": True,
            "web/orders.test.mts": True,
            "app/tests.py": True,
            "web/src/__tests__/foo.jsx": False,
            "tests/__init__.py": False,
            "tests/conftest.py": False,
            "tests/factories.py": False,
            "test/setup.ts": False,
            "web/src/__tests__/__init__.py": False,
            "web/src/__tests__/conftest.py": False,
            "app/models.py": False,
            "src/test_utils.ts": False,
            "src/orders_test.ts": False,
        }

        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(expected, source_paths.is_runnable_test_file(path))

    def test_jest_counts_script_files_under_a_tests_folder_and_not_their_support_files(self):
        cases = {
            "web/src/__tests__/foo.jsx": True,
            "web/src/__tests__/foo.mts": True,
            "web/src/__tests__/conftest.py": False,
            "web/src/foo.jsx": False,
        }

        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(expected, source_paths.is_runnable_test_file(path, counts_jest_tests_folder=True))


# Each column is the rule one gate reads: the size and review split and comment check (a test file), the coder
# packet's helper files and the pytest gate (runs alone), the jest gate, the manage.py test gate, and the full
# check's no-repair stop (a spec file).
TEST_FILE_RULE_COLUMNS = ("test_file", "runs_alone", "runs_under_jest", "runs_under_django", "spec_file")
TEST_FILE_RULE_CASES = {
    "app/tests/test_models.py": (True, True, True, True, False),
    "app/tests.py": (True, True, True, True, False),
    "app/orders_test.py": (True, True, True, False, False),
    "app/tests/factories.py": (True, False, False, False, False),
    "app/tests/conftest.py": (True, False, False, False, False),
    "app/testing_utils.py": (False, False, False, True, False),
    "web/orders.spec.ts": (True, True, True, False, True),
    "web/orders.test.ts": (True, True, True, False, False),
    "web/src/__tests__/render.tsx": (True, False, True, False, False),
    "web/fixtures/test_helpers.ts": (True, False, False, False, False),
    "app/models.py": (False, False, False, False, False),
}


class TestFileRuleTableTest(unittest.TestCase):
    def test_each_test_file_rule_answers_each_path_once(self):
        for path, expected in TEST_FILE_RULE_CASES.items():
            actual = (
                source_paths.is_test_path(path),
                source_paths.is_runnable_test_file(path),
                source_paths.is_runnable_test_file(path, counts_jest_tests_folder=True),
                source_paths.is_runnable_test_file(path, discovers_django_tests=True),
                source_paths.names_spec_file(path),
            )
            expected_rules = dict(zip(TEST_FILE_RULE_COLUMNS, expected, strict=True))
            actual_rules = dict(zip(TEST_FILE_RULE_COLUMNS, actual, strict=True))
            with self.subTest(path=path):
                self.assertEqual(expected_rules, actual_rules)

    def test_a_log_line_names_a_spec_file_only_when_one_of_its_words_is_a_spec_file_name(self):
        cases = {
            "FAIL web/orders.spec.ts:12:5 > checkout pays": True,
            "  at Object.<anonymous> (web/e2e/Login.SPEC.js:4:1)": True,
            "FAIL web/orders.test.ts": False,
            "see the spec. 1 failed": False,
        }

        for log_line, expected in cases.items():
            with self.subTest(log_line=log_line):
                self.assertEqual(expected, source_paths.names_spec_file(log_line))


if __name__ == "__main__":
    unittest.main()
