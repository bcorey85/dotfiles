"""A fail-closed gate whose import crashes exits 2 and names itself, instead of exiting 1 and letting the call run."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or toolkit_paths.SCRIPTS_DIR)
# The guarded gates that import lib/shell_command.py, with the name each stderr line opens with.
GATES = {"quality-check-cap": "gates/quality_check_cap.py", "git-discipline-gate": "gates/git_discipline_gate.py"}
PLANTED_MODULE = "lib/shell_command.py"
PAYLOAD = {"hook_event_name": "PreToolUse", "session_id": "s", "tool_name": "Bash", "tool_input": {"command": "ls"}}
# fork_write_scope imports lib/hook_input.py, not shell_command.py, so it is tested through it.
CODE_FORK_PAYLOAD = {**PAYLOAD, "tool_name": "Write", "agent_type": "code-fork",
                     "tool_input": {"file_path": "/tmp/outside.txt"}}
FORK_WRITE_SCOPE = ("gates/fork_write_scope.py", CODE_FORK_PAYLOAD)


class ImportGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.scripts = self.tmp / "scripts"
        shutil.copytree(SCRIPTS_DIR, self.scripts, ignore=shutil.ignore_patterns("__pycache__"))
        self.home = self.tmp / "home"
        self.home.mkdir()

    def run_gate(self, relative, payload=PAYLOAD, arguments=()):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home), "TMPDIR": str(self.tmp)}
        return subprocess.run([sys.executable, str(self.scripts / relative), *arguments], input=json.dumps(payload),
                              capture_output=True, text=True, env=env, cwd=str(self.tmp))

    def test_a_syntax_error_in_a_lib_module_blocks_each_gate_and_names_it(self):
        original = (self.scripts / PLANTED_MODULE).read_text()
        for name, relative in GATES.items():
            with self.subTest(gate=name):
                (self.scripts / PLANTED_MODULE).write_text(original)
                control = self.run_gate(relative)
                self.assertEqual(control.returncode, 0, control.stderr)
                (self.scripts / PLANTED_MODULE).write_text('x = "unterminated\n')

                crashed = self.run_gate(relative)

                self.assertEqual(crashed.returncode, 2, crashed.stderr)
                self.assertEqual(crashed.stdout, "", "a crashed gate prints no allow decision")
                self.assertIn(f"[{name}] crashed before it could read the call", crashed.stderr)
                self.assertIn("SyntaxError", crashed.stderr)
                self.assertIn("Recovery:", crashed.stderr)

    def test_a_syntax_error_in_a_lib_module_blocks_the_coder_gate_bash_hook(self):
        control = self.run_gate("code/coder_gate.py", arguments=("bash-hook",))
        self.assertEqual(control.returncode, 0, control.stderr)
        (self.scripts / PLANTED_MODULE).write_text('x = "unterminated\n')

        crashed = self.run_gate("code/coder_gate.py", arguments=("bash-hook",))

        self.assertEqual(crashed.returncode, 2, crashed.stderr)
        self.assertIn("[coder-gate] crashed before it could read the call", crashed.stderr)

    def test_a_runtime_crash_in_the_coder_gate_hook_blocks_and_names_the_gate(self):
        crashed = subprocess.run([sys.executable, str(self.scripts / "code/coder_gate.py"), "hook"], input="not json",
                                 capture_output=True, text=True, env={"PATH": os.environ["PATH"],
                                                                      "HOME": str(self.home)}, cwd=str(self.tmp))

        self.assertEqual(crashed.returncode, 2, crashed.stderr)
        self.assertIn("[coder-gate] crashed while judging the call", crashed.stderr)

    def test_the_coder_gate_cli_verbs_keep_their_traceback_after_the_guard_is_released(self):
        crashed = self.run_gate("code/coder_gate.py", arguments=("set", "--env"))

        self.assertNotEqual(crashed.returncode, 2, crashed.stderr)
        self.assertNotIn("crashed before it could read the call", crashed.stderr)

    def test_a_crash_in_git_destructive_calls_blocks_the_git_discipline_gate(self):
        planted = self.scripts / "lib/git_destructive_calls.py"
        control = self.run_gate(GATES["git-discipline-gate"])
        self.assertEqual(control.returncode, 0, control.stderr)
        planted.write_text('x = "unterminated\n')

        crashed = self.run_gate(GATES["git-discipline-gate"])

        self.assertEqual(crashed.returncode, 2, crashed.stderr)
        self.assertIn("[git-discipline-gate] crashed before it could read the call", crashed.stderr)

    def test_a_crash_in_hook_input_blocks_fork_write_scope(self):
        relative, payload = FORK_WRITE_SCOPE
        control = self.run_gate(relative, payload)
        self.assertEqual(control.returncode, 0, control.stderr)
        (self.scripts / "lib/hook_input.py").write_text('x = "unterminated\n')

        crashed = self.run_gate(relative, payload)

        self.assertEqual(crashed.returncode, 2, crashed.stderr)
        self.assertEqual(crashed.stdout, "", "a crashed gate prints no allow decision")
        self.assertIn("[fork-write-scope] crashed while judging the call", crashed.stderr)

    def test_a_crash_in_agent_names_blocks_fork_write_scope_for_every_write(self):
        relative, fork_payload = FORK_WRITE_SCOPE
        other_payload = {**fork_payload, "agent_type": "coder"}
        (self.scripts / "lib/agent_names.py").write_text('x = "unterminated\n')

        for label, payload in (("code-fork", fork_payload), ("coder", other_payload)):
            with self.subTest(agent_type=label):
                crashed = self.run_gate(relative, payload)

                self.assertEqual(crashed.returncode, 2, crashed.stderr)
                self.assertEqual(crashed.stdout, "", "a crashed gate prints no allow decision")
                self.assertIn("[fork-write-scope] crashed before it could read the call", crashed.stderr)

    def test_a_crash_in_hook_input_leaves_spec_budget_gate_open(self):
        # A size budget is not a safety gate: it fails open so Edit stays a route to repair the broken module.
        (self.scripts / "lib/hook_input.py").write_text('x = "unterminated\n')

        crashed = self.run_gate("gates/spec_budget_gate.py")

        self.assertNotEqual(crashed.returncode, 2, crashed.stderr)

    def test_a_system_exit_after_the_guard_keeps_its_own_code(self):
        script = self.tmp / "exits.py"
        script.write_text(f"import sys\nsys.path.insert(0, {str(self.scripts / 'lib')!r})\n"
                          "import import_guard\nimport_guard.guard('probe')\nsys.exit(3)\n")
        finished = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
        self.assertEqual((finished.returncode, finished.stderr), (3, ""))

    def test_a_gate_imported_as_a_library_keeps_its_own_excepthook(self):
        guarded_gates = {**GATES, "fork-write-scope": FORK_WRITE_SCOPE[0]}
        for name, relative in guarded_gates.items():
            with self.subTest(gate=name):
                gate_path = self.scripts / relative
                script = self.tmp / "imports_gate.py"
                script.write_text(f"import sys\nhook = sys.excepthook\n"
                                  f"sys.path.insert(0, {str(gate_path.parent)!r})\n"
                                  f"import {gate_path.stem}\nsys.exit(0 if sys.excepthook is hook else 7)\n")
                finished = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
                self.assertEqual((finished.returncode, finished.stderr), (0, ""))

    def test_a_missing_name_in_a_lib_module_blocks_the_gate(self):
        (self.scripts / "lib/git_calls.py").write_text("")
        crashed = self.run_gate(GATES["git-discipline-gate"])
        self.assertEqual(crashed.returncode, 2, crashed.stderr)
        self.assertIn("[git-discipline-gate] crashed", crashed.stderr)
        self.assertIn("ImportError", crashed.stderr)


if __name__ == "__main__":
    unittest.main()
