import os
import sys
import unittest
import unittest.mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.SCRIPTS_DIR))
import hook_input


class HookNameTest(unittest.TestCase):
    def test_a_snake_case_script_file_reports_its_kebab_case_hook_name(self):
        script = os.path.join("scripts", "git_discipline_gate.py")

        with unittest.mock.patch.object(sys, "argv", [script]):
            self.assertEqual("git-discipline-gate", hook_input.hook_name())

    def test_a_hook_run_with_no_script_name_reports_hook(self):
        with unittest.mock.patch.object(sys, "argv", [""]):
            self.assertEqual("hook", hook_input.hook_name())


if __name__ == "__main__":
    unittest.main()
