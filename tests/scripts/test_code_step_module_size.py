"""code_step_boundary.py stays under the module size cap, and the state store never imports code_step_core."""
import ast
import unittest

import toolkit_paths

MODULE_LINE_CAP = 1000


class CodeStepModuleSizeTest(unittest.TestCase):
    def test_code_step_boundary_is_under_the_module_line_cap(self):
        boundary = toolkit_paths.CODE_DIR / "code_step_boundary.py"
        line_count = len(boundary.read_text().splitlines())

        self.assertLess(line_count, MODULE_LINE_CAP)

    def test_the_state_store_is_its_own_module_that_never_imports_code_step_core(self):
        store = toolkit_paths.CODE_DIR / "code_step_store.py"
        tree = ast.parse(store.read_text())

        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                imported_modules.add(node.module)

        self.assertNotIn("code_step_core", imported_modules)


if __name__ == "__main__":
    unittest.main()
