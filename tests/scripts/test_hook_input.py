import os
import sys
import unittest
import unittest.mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import hook_input


class HookNameTest(unittest.TestCase):
    def test_a_snake_case_script_file_reports_its_kebab_case_hook_name(self):
        script = os.path.join("scripts", "git_discipline_gate.py")

        with unittest.mock.patch.object(sys, "argv", [script]):
            self.assertEqual("git-discipline-gate", hook_input.hook_name())

    def test_a_hook_run_with_no_script_name_reports_hook(self):
        with unittest.mock.patch.object(sys, "argv", [""]):
            self.assertEqual("hook", hook_input.hook_name())


class TempDirTest(unittest.TestCase):
    def test_tmp_and_the_tmpdir_variable_are_temp_roots(self):
        with unittest.mock.patch.dict(os.environ, {"TMPDIR": "/var/tmp"}):
            self.assertTrue(hook_input.is_under_temp_dir("/tmp/a/b.log"))
            self.assertTrue(hook_input.is_under_temp_dir("/var/tmp/b.log"))
            self.assertFalse(hook_input.is_under_temp_dir("/tmpfoo/b.log"))
            self.assertFalse(hook_input.is_under_temp_dir("/home/user/b.log"))

    def test_var_tmp_is_a_temp_root_whatever_tmpdir_names(self):
        with unittest.mock.patch.dict(os.environ, {"TMPDIR": "/tmp"}):
            self.assertTrue(hook_input.is_under_temp_dir("/var/tmp/clippy/run.log"))


class ExpandEnvNamesTest(unittest.TestCase):
    def test_only_the_named_set_variables_are_replaced(self):
        env = {"TMPDIR": "/t", "HOME": "/h"}
        with unittest.mock.patch.dict(os.environ, env):
            os.environ.pop("GONE", None)
            self.assertEqual("/t/a /h/b ${OTHER}/c $TMPDIRX",
                             hook_input.expand_env_names("$TMPDIR/a ${HOME}/b ${OTHER}/c $TMPDIRX",
                                                         ("TMPDIR", "HOME")))
            self.assertEqual("$GONE/x", hook_input.expand_env_names("$GONE/x", ("GONE",)))


if __name__ == "__main__":
    unittest.main()
