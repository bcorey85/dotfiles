import os
import sys
import unittest
import unittest.mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import hook_input

# A base no system temp dir uses, so a root under it exists only when the CLAUDE_CODE_TMPDIR branch adds it.
UNIQUE_BASE = "/nonexistent-cct"


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


class SessionTempRootsTest(unittest.TestCase):
    def roots_with(self, env):
        with unittest.mock.patch.dict(os.environ, env):
            for name in ("TMPDIR", "CLAUDE_CODE_TMPDIR"):
                if name not in env:
                    os.environ.pop(name, None)
            return hook_input.session_temp_roots()

    def test_tmpdir_and_claude_code_tmpdir_each_add_a_root_when_set(self):
        folder = f"claude-{os.getuid()}"
        unset = self.roots_with({})
        with_tmpdir = self.roots_with({"TMPDIR": "/var/tmp"})
        with_code_tmpdir = self.roots_with({"CLAUDE_CODE_TMPDIR": UNIQUE_BASE})

        self.assertIn(os.path.realpath("/tmp/" + folder), unset)
        self.assertEqual(with_tmpdir, [*unset, os.path.realpath("/var/tmp/" + folder)])
        self.assertNotIn(os.path.realpath(f"{UNIQUE_BASE}/{folder}"), unset)
        self.assertIn(os.path.realpath(f"{UNIQUE_BASE}/{folder}"), with_code_tmpdir)

    def test_the_forms_text_names_the_same_three_roots_the_function_builds(self):
        folder = f"claude-{os.getuid()}"
        cases = (
            ("/tmp/claude-<uid>/", {}, os.path.realpath("/tmp/" + folder)),
            ("$TMPDIR/claude-<uid>/", {"TMPDIR": "/var/tmp"}, os.path.realpath("/var/tmp/" + folder)),
            ("$CLAUDE_CODE_TMPDIR/claude-<uid>/", {"CLAUDE_CODE_TMPDIR": UNIQUE_BASE},
             os.path.realpath(f"{UNIQUE_BASE}/{folder}")),
        )
        for form, env, root in cases:
            with self.subTest(form):
                self.assertIn(form, hook_input.SESSION_TEMP_ROOT_FORMS)
                self.assertIn(root, self.roots_with(env))

    def test_a_path_under_a_session_root_is_under_one(self):
        folder = f"claude-{os.getuid()}"
        with unittest.mock.patch.dict(os.environ, {"CLAUDE_CODE_TMPDIR": UNIQUE_BASE}):
            self.assertTrue(hook_input.is_under_session_temp_root(f"{UNIQUE_BASE}/{folder}/a/brief.md"))
            self.assertFalse(hook_input.is_under_session_temp_root(f"{UNIQUE_BASE}/other/brief.md"))


class SessionScratchpadTest(unittest.TestCase):
    def test_only_a_path_below_the_slug_and_session_folders_is_in_the_scratchpad(self):
        root = f"{UNIQUE_BASE}/claude-{os.getuid()}"
        cases = (
            (f"{root}/-proj/s2/scratchpad/repo", True),
            (f"{root}/-proj/s2/x", True),
            (f"{root}/-proj/s2", False),
            (f"{root}/s2/x", False),
            (f"{root}/-proj/s3/scratchpad/repo", False),
            (f"{UNIQUE_BASE}/other/-proj/s2/x", False),
        )
        with unittest.mock.patch.dict(os.environ, {"CLAUDE_CODE_TMPDIR": UNIQUE_BASE}):
            for path, expected in cases:
                with self.subTest(path=path):
                    self.assertEqual(expected, hook_input.is_in_session_scratchpad(path, "s2"))


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
