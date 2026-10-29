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


if __name__ == "__main__":
    unittest.main()
