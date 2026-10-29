"""code_step_boundary.py stays under the module size cap."""
import unittest

import toolkit_paths

MODULE_LINE_CAP = 1000


class CodeStepModuleSizeTest(unittest.TestCase):
    def test_code_step_boundary_is_under_the_module_line_cap(self):
        boundary = toolkit_paths.CODE_DIR / "code_step_boundary.py"
        line_count = len(boundary.read_text().splitlines())

        self.assertLess(line_count, MODULE_LINE_CAP)


if __name__ == "__main__":
    unittest.main()
