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


if __name__ == "__main__":
    unittest.main()
