"""Tests for coder_gate.py: the variables a gate runs its commands with, the scope of a check command (whole suite,
targeted, unresolved), how a make target or docker call is resolved, and the refusal the bash hook gives."""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
REAL_CLAUDE = pathlib.Path(os.environ.get("CODE_STEP_REAL_CLAUDE") or HERE.parent.parent / "claude" / ".claude")
GATE_SCRIPT = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or REAL_CLAUDE / "scripts" / "code") / "coder_gate.py"
GIT_IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
                "GIT_COMMITTER_EMAIL": "t@example.com"}
sys.path.insert(0, str(GATE_SCRIPT.parent.parent / "lib"))
import check_scope  # noqa: E402
import script_utils  # noqa: E402
import toolkit_paths  # noqa: E402


def commands_with(coder, outcome):
    return list(script_utils.details_with_outcome(coder["commands"], outcome))


class CoderGateEnvironmentTests(unittest.TestCase):
    def setUp(self):
        temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temp_directory.cleanup)
        self.repo = pathlib.Path(temp_directory.name) / "repo"
        self.repo.mkdir()
        self.home = pathlib.Path(temp_directory.name) / "home"
        self.home.mkdir()
        self.env = {**os.environ, **GIT_IDENTITY, "HOME": str(self.home), "CLAUDE_TOOLKIT_TELEMETRY": "0"}
        self.env.pop("GATE_PROBE", None)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True, env=self.env)

    def gate_set(self, *arguments):
        return subprocess.run([sys.executable, "-B", str(GATE_SCRIPT), "set", *arguments], cwd=self.repo, env=self.env,
                              capture_output=True, text=True)

    def gate_hook(self):
        event = {"agent_type": "coder", "agent_id": "a1", "cwd": str(self.repo),
                 "tool_input": {"message": "BEHAVIOR: done"}}
        return subprocess.run([sys.executable, "-B", str(GATE_SCRIPT), "hook"], cwd=self.repo, env=self.env,
                              input=json.dumps(event), capture_output=True, text=True)

    def stored_gate(self):
        return json.loads((self.repo / ".git/coder-gate.json").read_text())

    def test_the_hook_lets_a_coder_through_silently_when_no_gate_is_set(self):
        done = self.gate_hook()

        self.assertEqual(0, done.returncode)
        self.assertEqual("", done.stdout)
        self.assertEqual("", done.stderr)

    def test_set_stores_each_variable_with_its_value_unquoted(self):
        done = self.gate_set("--env", "A=1", "--env", 'B="two words"', "--env", "C='x y'", "--env", "D=",
                             "python3 -m pytest tests/test_one.py")

        self.assertEqual(0, done.returncode, done.stderr)
        self.assertEqual({"A": "1", "B": "two words", "C": "x y", "D": ""}, self.stored_gate()["env"])
        self.assertEqual(["python3 -m pytest tests/test_one.py"], self.stored_gate()["commands"])

    def test_set_refuses_a_word_that_is_not_a_variable_assignment(self):
        for word in ("not-an-assignment", "A=1 B=2", "=1", "A='unclosed"):
            with self.subTest(word=word):
                done = self.gate_set("--env", word, "python3 -m pytest tests/test_one.py")

                self.assertNotEqual(0, done.returncode)
                self.assertIn("--env needs NAME=value", done.stderr)

    def test_set_refuses_a_trailing_env_flag_with_no_value(self):
        for arguments in (("python3 -m pytest tests/test_one.py", "--env"), ("--env", "A=1", "--env"), ("--env",)):
            with self.subTest(arguments=arguments):
                done = self.gate_set(*arguments)

                self.assertNotEqual(0, done.returncode)
                self.assertIn("--env needs NAME=value", done.stderr)
                self.assertFalse((self.repo / ".git/coder-gate.json").exists())

    def test_the_hook_runs_each_command_with_the_stored_variables(self):
        probe = 'test "$GATE_PROBE" = "two words"'
        self.gate_set("--env", 'GATE_PROBE="two words"', probe, f"cd . && {probe}")

        done = self.gate_hook()

        self.assertEqual(0, done.returncode, done.stderr)
        self.assertEqual("pass", self.stored_gate()["coders"]["a1"]["result"])

    def test_the_hook_denies_a_command_that_needs_a_variable_the_gate_was_not_given(self):
        self.gate_set('test "$GATE_PROBE" = 1')

        done = self.gate_hook()

        self.assertEqual("deny", self.stored_gate()["coders"]["a1"]["result"])
        self.assertIn("deny", done.stdout)

    def test_set_judges_a_make_command_from_the_repo_root_the_gate_runs_it_in(self):
        (self.repo / "Makefile").write_text("test:\n\tpytest\n")
        (self.repo / "sub").mkdir()

        for folder in (self.repo, self.repo / "sub"):
            with self.subTest(folder=folder):
                done = subprocess.run([sys.executable, "-B", str(GATE_SCRIPT), "set", "make test"], cwd=folder,
                                      env=self.env, capture_output=True, text=True)

                self.assertNotEqual(0, done.returncode)
                self.assertIn("refused", done.stderr)
        self.assertFalse((self.repo / ".git/coder-gate.json").exists())

        accepted = self.gate_set("make test FILE=x")

        self.assertEqual(0, accepted.returncode, accepted.stderr)

    def test_set_names_the_target_and_recipe_command_the_bash_hook_names(self):
        (self.repo / "Makefile").write_text("test:\n\t@PYTHONPATH=. pytest\n")
        event = {"agent_type": "coder", "cwd": str(self.repo), "tool_input": {"command": "make test"}}

        refused = self.gate_set("python3 -m pytest tests/a.py", "make test", "ruff check src/a.py")
        hook = subprocess.run([sys.executable, "-B", str(GATE_SCRIPT), "bash-hook"], input=json.dumps(event),
                              env=self.env, capture_output=True, text=True)

        recipe_line = "`make test` runs `PYTHONPATH=. pytest` in target `test`."
        hook_reason = json.loads(hook.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn(recipe_line, hook_reason)
        self.assertIn(f"  make test\n    {recipe_line}\n", refused.stderr)
        self.assertNotIn("tests/a.py", refused.stderr)
        self.assertNotIn("src/a.py", refused.stderr)

    def test_set_refuses_a_make_command_from_a_repository_with_no_work_tree(self):
        bare_repo = self.repo.parent / "bare.git"
        subprocess.run(["git", "init", "-q", "--bare", str(bare_repo)], check=True, env=self.env)

        done = subprocess.run([sys.executable, "-B", str(GATE_SCRIPT), "set", "make test"], cwd=bare_repo,
                              env=self.env, capture_output=True, text=True)

        self.assertNotEqual(0, done.returncode)
        self.assertIn("must run inside a git work tree", done.stderr)
        self.assertNotIn("Traceback", done.stderr)

    def gate_hook_with_timeout(self, timeout_seconds):
        # Runs the hook in this process, so the timeout constant can be set; returns what the hook printed.
        gate = load_gate_module()
        gate.COMMAND_TIMEOUT_SECONDS = timeout_seconds
        event = {"agent_type": "coder", "agent_id": "a1", "cwd": str(self.repo),
                 "tool_input": {"message": "BEHAVIOR: done"}}
        printed = io.StringIO()
        with mock.patch.dict(os.environ, self.env), mock.patch.object(sys, "stdin", io.StringIO(json.dumps(event))), \
                contextlib.redirect_stdout(printed):
            gate.run_hook()
        return printed.getvalue()

    def test_the_hook_allows_a_gate_whose_only_command_timed_out_and_stamps_the_timeout(self):
        command = "echo FAILED test_one; sleep 5"
        self.gate_set(command)

        printed = self.gate_hook_with_timeout(1)

        coder = self.stored_gate()["coders"]["a1"]
        self.assertEqual("timeout", coder["result"])
        self.assertEqual([], commands_with(coder, "failed"))
        self.assertEqual([command], commands_with(coder, "timed-out"))
        output = json.loads(printed)["hookSpecificOutput"]
        self.assertEqual("allow", output["permissionDecision"])
        message = output["updatedInput"]["message"]
        self.assertIn(f"`{command}`", message)
        self.assertIn(f"`{command}`, timed out after 1 s", message)
        self.assertIn("timed out with no test result", message)
        self.assertIn("they are not among the failures", message)
        self.assertIn("FAILED test_one", message)
        cleared = subprocess.run([sys.executable, "-B", str(GATE_SCRIPT), "clear"], cwd=self.repo, env=self.env,
                                 capture_output=True, text=True)
        self.assertIn(f"failed: none, timed out (no test result): {command}", cleared.stdout)

    def test_the_hook_still_denies_a_real_failure_that_ran_beside_a_timeout(self):
        self.gate_set("sleep 5", "exit 3")

        printed = self.gate_hook_with_timeout(1)

        coder = self.stored_gate()["coders"]["a1"]
        self.assertEqual("deny", coder["result"])
        self.assertEqual(["exit 3"], commands_with(coder, "failed"))
        self.assertEqual(["sleep 5"], commands_with(coder, "timed-out"))
        self.assertEqual("deny", json.loads(printed)["hookSpecificOutput"]["permissionDecision"])

    def gate_hook_with_budget(self, budget_seconds, min_command_seconds=1):
        # Runs the hook in this process with a gate budget and a smallest start; returns what it printed.
        gate = load_gate_module()
        gate.GATE_BUDGET_SECONDS = budget_seconds
        gate.MIN_COMMAND_SECONDS = min_command_seconds
        event = {"agent_type": "coder", "agent_id": "a1", "cwd": str(self.repo),
                 "tool_input": {"message": "BEHAVIOR: done"}}
        printed = io.StringIO()
        with mock.patch.dict(os.environ, self.env), mock.patch.object(sys, "stdin", io.StringIO(json.dumps(event))), \
                contextlib.redirect_stdout(printed):
            gate.run_hook()
        return printed.getvalue()

    def test_a_run_over_the_time_budget_names_the_commands_it_did_not_start_and_ends_with_a_verdict(self):
        self.gate_set("sleep 10", "echo second", "echo third")
        started = time.monotonic()

        printed = self.gate_hook_with_budget(2)

        self.assertLess(time.monotonic() - started, 8)
        coder = self.stored_gate()["coders"]["a1"]
        self.assertEqual("timeout", coder["result"])
        self.assertEqual(["sleep 10"], commands_with(coder, "timed-out"))
        self.assertEqual(["echo second", "echo third"], commands_with(coder, "not-started"))
        output = json.loads(printed)["hookSpecificOutput"]
        self.assertEqual("allow", output["permissionDecision"])
        message = output["updatedInput"]["message"]
        self.assertIn("HAND-BACK GATE TIME BUDGET", message)
        self.assertIn("`sleep 10`, timed out after 2 s", message)
        self.assertIn("`echo second`", message)
        self.assertIn("`echo third`", message)
        cleared = subprocess.run([sys.executable, "-B", str(GATE_SCRIPT), "clear"], cwd=self.repo, env=self.env,
                                 capture_output=True, text=True)
        self.assertIn("not started (time budget used up): echo second, echo third", cleared.stdout)

    def test_a_command_the_budget_leaves_no_time_for_is_not_started_and_none_timed_out(self):
        self.gate_set("sleep 2", "echo second")

        printed = self.gate_hook_with_budget(4, min_command_seconds=3)

        coder = self.stored_gate()["coders"]["a1"]
        self.assertEqual("timeout", coder["result"])
        self.assertEqual(["echo second"], commands_with(coder, "not-started"))
        self.assertEqual([], commands_with(coder, "timed-out"))
        self.assertEqual("allow", json.loads(printed)["hookSpecificOutput"]["permissionDecision"])

    def test_the_gate_budget_ends_before_the_hook_timeout_with_margin(self):
        gate = load_gate_module()
        settings = json.loads((toolkit_paths.CLAUDE_DIR / "settings.json").read_text())
        timeouts = [handler["timeout"]
                    for group in settings["hooks"]["PreToolUse"] if group.get("matcher") == "SubagentHandback"
                    for handler in group["hooks"] if "coder_gate.py hook" in handler.get("command", "")]

        self.assertEqual([gate.HOOK_TIMEOUT_SECONDS], timeouts)
        self.assertGreaterEqual(gate.HOOK_TIMEOUT_SECONDS - gate.GATE_BUDGET_SECONDS, 600)

    def test_a_gate_cleared_during_the_lock_wait_lets_the_hand_back_through(self):
        gate = load_gate_module()
        self.gate_set("echo first")
        event = {"agent_type": "coder", "agent_id": "a1", "cwd": str(self.repo),
                 "tool_input": {"message": "BEHAVIOR: done"}}
        gate_file = self.repo / ".git/coder-gate.json"

        def clear_while_waiting(lock_file, operation):
            gate_file.unlink()

        printed = io.StringIO()
        with mock.patch.dict(os.environ, self.env), \
                mock.patch.object(gate.fcntl, "flock", side_effect=clear_while_waiting), \
                mock.patch.object(sys, "stdin", io.StringIO(json.dumps(event))), \
                contextlib.redirect_stdout(printed):
            gate.run_hook()

        self.assertEqual("", printed.getvalue())
        self.assertFalse(gate_file.exists())

    def test_a_gate_set_again_during_the_lock_wait_lets_the_hand_back_through(self):
        gate = load_gate_module()
        event = {"agent_type": "coder", "agent_id": "a1", "cwd": str(self.repo),
                 "tool_input": {"message": "BEHAVIOR: done"}}
        gate_file = self.repo / ".git/coder-gate.json"

        for changed_key, new_value in (("setAt", time.time() + 5), ("dispatchId", "other"), ("runId", "other")):
            with self.subTest(changed_key=changed_key):
                self.gate_set("echo first")

                def set_again_while_waiting(lock_file, operation, key=changed_key, value=new_value):
                    rewritten = json.loads(gate_file.read_text())
                    rewritten[key] = value
                    gate_file.write_text(json.dumps(rewritten))

                printed = io.StringIO()
                with mock.patch.dict(os.environ, self.env), \
                        mock.patch.object(gate.fcntl, "flock", side_effect=set_again_while_waiting), \
                        mock.patch.object(sys, "stdin", io.StringIO(json.dumps(event))), \
                        contextlib.redirect_stdout(printed):
                    gate.run_hook()

                self.assertEqual("", printed.getvalue())
                self.assertEqual({}, self.stored_gate()["coders"])

    def test_set_refuses_a_key_flag_with_no_value_or_after_the_command(self):
        cases = ((("true", "--run", "R"), "--run goes before the command"),
                 (("--run",), "--run needs a value"),
                 (("--run", "R", "true", "--dispatch"), "--dispatch goes before the command"))

        for arguments, message in cases:
            with self.subTest(arguments=arguments):
                done = self.gate_set(*arguments)

                self.assertNotEqual(0, done.returncode)
                self.assertIn(message, done.stderr)

    def write_launch(self, run_id, agent_id, dispatch_id):
        events_file = self.repo / ".git/code-step/runs" / run_id / "events.jsonl"
        events_file.parent.mkdir(parents=True, exist_ok=True)
        row = {"v": 1, "ts": time.time(), "event": "launch", "session_id": "s", "agent_id": agent_id,
               "dispatch": dispatch_id}
        with events_file.open("a") as log_file:
            log_file.write(json.dumps(row) + "\n")

    def test_a_keyed_gate_gates_only_the_coder_launched_for_its_run_and_dispatch(self):
        self.write_launch("run-1", "a1", "d1")
        self.write_launch("run-1", "a2", "d2")
        self.write_launch("run-2", "a3", "d1")
        cases = (("a1", True, "launched for the gate's dispatch"),
                 ("a1", True, "the same coder resumed, handing back a second time"),
                 ("a2", False, "launched for another dispatch of the run"),
                 ("a3", False, "launched for another run"),
                 ("a4", False, "no launch on record"))
        done = self.gate_set("--run", "run-1", "--dispatch", "d1", "true")
        self.assertEqual(0, done.returncode, done.stderr)

        for agent_id, is_gated, reason in cases:
            with self.subTest(reason):
                event = {"agent_type": "coder", "agent_id": agent_id, "cwd": str(self.repo),
                         "tool_input": {"message": "BEHAVIOR: done"}}
                hook = subprocess.run([sys.executable, "-B", str(GATE_SCRIPT), "hook"], cwd=self.repo, env=self.env,
                                      input=json.dumps(event), capture_output=True, text=True)

                self.assertEqual(0, hook.returncode, hook.stderr)
                self.assertEqual(is_gated, agent_id in self.stored_gate()["coders"], reason)
                self.assertEqual(is_gated, bool(hook.stdout.strip()), reason)

    def test_set_refuses_a_run_without_a_dispatch(self):
        done = self.gate_set("--run", "run-1", "true")

        self.assertNotEqual(0, done.returncode)
        self.assertIn("--run and --dispatch go together", done.stderr)

    def test_a_missing_program_is_a_setup_fault_that_allows_the_hand_back_and_names_the_command(self):
        command = "no-such-runner-for-the-gate pytest tests/test_one.py"
        self.gate_set(command)

        hook = self.gate_hook()

        coder = self.stored_gate()["coders"]["a1"]
        self.assertEqual("setup-fault", coder["result"])
        self.assertEqual(0, coder["denies"])
        self.assertEqual([], commands_with(coder, "failed"))
        self.assertEqual([command], commands_with(coder, "setup-fault"))
        output = json.loads(hook.stdout)["hookSpecificOutput"]
        self.assertEqual("allow", output["permissionDecision"])
        message = output["updatedInput"]["message"]
        self.assertIn("HAND-BACK GATE SETUP FAULT", message)
        self.assertIn(f"`{command}`", message)
        self.assertIn("they are not among the failures", message)

    def test_a_module_missing_from_outside_the_repo_never_spends_a_deny(self):
        self.gate_set("""echo "ModuleNotFoundError: No module named 'sqlalchemy'"; exit 2""")

        for _ in range(4):
            hook = self.gate_hook()
            self.assertEqual("allow", json.loads(hook.stdout)["hookSpecificOutput"]["permissionDecision"])

        coder = self.stored_gate()["coders"]["a1"]
        self.assertEqual("setup-fault", coder["result"])
        self.assertEqual(0, coder["denies"])

    def test_a_missing_repo_module_or_a_missing_module_beside_a_failed_test_still_denies(self):
        (self.repo / "app").mkdir()
        commands = {
            "repo module": """echo "ModuleNotFoundError: No module named 'app.models'"; exit 2""",
            "failed test": """echo "No module named 'yaml'"; echo "1 failed, 2 passed"; exit 1""",
        }
        for case, command in commands.items():
            with self.subTest(case=case):
                (self.repo / ".git/coder-gate.json").unlink(missing_ok=True)
                self.gate_set(command)

                hook = self.gate_hook()

                self.assertEqual("deny", json.loads(hook.stdout)["hookSpecificOutput"]["permissionDecision"])
                self.assertEqual([command], commands_with(self.stored_gate()["coders"]["a1"], "failed"))

    def test_a_denial_lists_the_failing_test_that_the_output_tail_cut_off(self):
        self.gate_set("""echo "FAIL: test_x (app.tests.T)"; seq 1 3000; exit 1""")

        hook = self.gate_hook()

        reason = json.loads(hook.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("Failing tests:\nFAIL: test_x (app.tests.T)", reason)

    def test_a_django_settings_error_under_pytest_is_a_setup_fault(self):
        commands = {
            "improperly configured": """echo "django.core.exceptions.ImproperlyConfigured: bad"; echo pytest; exit 1""",
            "settings not configured": """echo "INSTALLED_APPS, settings are not configured."; echo pytest; exit 2""",
            "apps not loaded": """echo "AppRegistryNotReady: Apps aren't loaded yet."; echo pytest; exit 2""",
        }
        for case, command in commands.items():
            with self.subTest(case=case):
                (self.repo / ".git/coder-gate.json").unlink(missing_ok=True)
                self.gate_set(command)

                hook = self.gate_hook()

                coder = self.stored_gate()["coders"]["a1"]
                self.assertEqual("setup-fault", coder["result"])
                self.assertEqual(0, coder["denies"])
                self.assertEqual([command], commands_with(coder, "setup-fault"))
                self.assertEqual("allow", json.loads(hook.stdout)["hookSpecificOutput"]["permissionDecision"])

    def test_a_django_settings_error_denies_when_the_coder_changed_a_settings_module_or_app_config(self):
        command = """echo "django.core.exceptions.ImproperlyConfigured: bad"; echo pytest; exit 1"""
        changed_paths = ("app/settings.py", "app/settings/base.py", "app/apps.py", "app/test_settings.py")
        for changed_path in changed_paths:
            with self.subTest(changed_path=changed_path):
                (self.repo / ".git/coder-gate.json").unlink(missing_ok=True)
                (self.repo / changed_path).parent.mkdir(parents=True, exist_ok=True)
                (self.repo / changed_path).write_text("DEBUG = True\n")
                self.gate_set(command)

                hook = self.gate_hook()

                self.assertEqual("deny", json.loads(hook.stdout)["hookSpecificOutput"]["permissionDecision"])
                self.assertEqual([command], commands_with(self.stored_gate()["coders"]["a1"], "failed"))
                (self.repo / changed_path).unlink()

    def test_a_django_settings_error_stays_a_setup_fault_when_the_coder_changed_other_files(self):
        command = """echo "django.core.exceptions.ImproperlyConfigured: bad"; echo pytest; exit 1"""
        (self.repo / "app").mkdir()
        (self.repo / "app/models.py").write_text("x = 1\n")
        self.gate_set(command)

        self.gate_hook()

        self.assertEqual("setup-fault", self.stored_gate()["coders"]["a1"]["result"])

    def test_a_settings_error_beside_a_failed_test_a_syntax_error_or_under_manage_py_test_still_denies(self):
        commands = {
            "failed test": """echo "ImproperlyConfigured: x"; echo pytest; echo "1 failed, 2 passed"; exit 1""",
            "syntax error": """echo pytest; echo "SyntaxError: bad"; echo "settings are not configured"; exit 2""",
            "manage.py test": """echo "ImproperlyConfigured: bad"; echo manage.py test; exit 1""",
        }
        for case, command in commands.items():
            with self.subTest(case=case):
                (self.repo / ".git/coder-gate.json").unlink(missing_ok=True)
                self.gate_set(command)

                hook = self.gate_hook()

                self.assertEqual("deny", json.loads(hook.stdout)["hookSpecificOutput"]["permissionDecision"])
                self.assertEqual([command], commands_with(self.stored_gate()["coders"]["a1"], "failed"))

    def test_a_manage_py_test_run_that_exits_0_after_running_no_test_is_a_setup_fault_not_a_pass(self):
        (self.repo / "manage.py").write_text('print("Ran 0 tests in 0.000s")\n')
        command = "python3 manage.py test app.tests"
        self.gate_set(command)

        hook = self.gate_hook()

        coder = self.stored_gate()["coders"]["a1"]
        self.assertEqual("setup-fault", coder["result"])
        self.assertEqual([command], commands_with(coder, "setup-fault"))
        self.assertEqual("allow", json.loads(hook.stdout)["hookSpecificOutput"]["permissionDecision"])

    def test_a_manage_py_test_run_that_ran_tests_passes(self):
        command = """echo manage.py test; echo "Ran 10 tests in 0.1s"; exit 0"""
        self.gate_set(command)

        self.gate_hook()

        self.assertEqual("pass", self.stored_gate()["coders"]["a1"]["result"])

    def test_a_real_failure_beside_a_setup_fault_denies_with_only_the_real_failure(self):
        self.gate_set("exit 127", "echo assertion-broke; exit 3")

        hook = self.gate_hook()

        coder = self.stored_gate()["coders"]["a1"]
        self.assertEqual("deny", coder["result"])
        self.assertEqual(["echo assertion-broke; exit 3"], commands_with(coder, "failed"))
        self.assertEqual(["exit 127"], commands_with(coder, "setup-fault"))
        reason = json.loads(hook.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("assertion-broke", reason)
        self.assertNotIn("`exit 127`", reason)

    def test_a_missing_test_path_is_a_command_error_that_never_spends_a_deny(self):
        commands = {
            "pytest": """echo "ERROR: file or directory not found: backend/app/tests/test_x.py"; exit 4""",
            "python script": "python3 missing/manage.py test app.tests",
        }
        for case, command in commands.items():
            with self.subTest(case=case):
                (self.repo / ".git/coder-gate.json").unlink(missing_ok=True)
                self.gate_set(command)

                for _ in range(4):
                    hook = self.gate_hook()
                    self.assertEqual("allow", json.loads(hook.stdout)["hookSpecificOutput"]["permissionDecision"])

                coder = self.stored_gate()["coders"]["a1"]
                self.assertEqual("command-error", coder["result"])
                self.assertEqual(0, coder["denies"])
                self.assertEqual([], commands_with(coder, "failed"))
                self.assertEqual([command], commands_with(coder, "command-error"))
                message = json.loads(hook.stdout)["hookSpecificOutput"]["updatedInput"]["message"]
                self.assertIn("HAND-BACK GATE COMMAND ERROR", message)
                self.assertIn(f"`{command}`: ", message)
                self.assertIn("they are not among the failures and spent no denial", message)

    def test_a_missing_path_line_for_a_path_that_exists_still_denies(self):
        (self.repo / "tests").mkdir()
        (self.repo / "tests/test_x.py").write_text("")
        command = """echo "ERROR: file or directory not found: tests/test_x.py"; exit 4"""
        self.gate_set(command)

        hook = self.gate_hook()

        self.assertEqual("deny", json.loads(hook.stdout)["hookSpecificOutput"]["permissionDecision"])
        self.assertEqual([command], commands_with(self.stored_gate()["coders"]["a1"], "failed"))

    def test_a_real_failure_beside_a_command_error_denies_with_only_the_real_failure(self):
        missing = "python3 missing/manage.py test app.tests"
        self.gate_set(missing, "echo assertion-broke; exit 3")

        hook = self.gate_hook()

        coder = self.stored_gate()["coders"]["a1"]
        self.assertEqual("deny", coder["result"])
        self.assertEqual(["echo assertion-broke; exit 3"], commands_with(coder, "failed"))
        self.assertEqual([missing], commands_with(coder, "command-error"))
        self.assertNotIn(f"`{missing}`", json.loads(hook.stdout)["hookSpecificOutput"]["permissionDecisionReason"])

    def test_a_setup_fault_beside_a_command_error_gets_the_same_outcome_from_the_scoped_run_and_the_hook(self):
        setup_fault = "exit 127"
        command_error = "python3 missing/manage.py test app.tests"
        log_path = self.repo / "scoped-tests.log"
        self.gate_set(setup_fault, command_error)

        self.gate_hook()
        scoped_result, _tails = load_gate_module().run_scoped_tests(str(self.repo), [setup_fault, command_error], (),
                                                                    log_path)

        hook_outcome = self.stored_gate()["coders"]["a1"]["result"]
        scoped_outcome = scoped_result.split(":")[0].replace(" ", "-")
        self.assertEqual("command-error", hook_outcome)
        self.assertEqual(hook_outcome, scoped_outcome, scoped_result)

    def test_a_coder_stored_with_the_old_command_lists_keeps_its_counts_and_gets_the_commands_map(self):
        command = "echo ok"
        self.gate_set(command)
        gate = self.stored_gate()
        gate["coders"]["a1"] = {"runs": 2, "denies": 1, "failed": ["old"], "skipped": [], "timed_out": [],
                                "setup_faults": ["old"], "command_errors": [], "result": "deny"}
        (self.repo / ".git/coder-gate.json").write_text(json.dumps(gate))

        self.gate_hook()

        coder = self.stored_gate()["coders"]["a1"]
        self.assertEqual({"runs": 3, "denies": 1, "result": "pass", "commands": {}}, coder)

    def test_a_gate_stored_before_variables_existed_still_runs(self):
        self.gate_set("true")
        gate = self.stored_gate()
        del gate["env"]
        (self.repo / ".git/coder-gate.json").write_text(json.dumps(gate))

        self.gate_hook()

        self.assertEqual("pass", self.stored_gate()["coders"]["a1"]["result"])


class RunCommandsTests(unittest.TestCase):
    def setUp(self):
        temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temp_directory.cleanup)
        self.repo = pathlib.Path(temp_directory.name)
        self.gate = load_gate_module()

    def run_gate_commands(self, *commands, env=None):
        return self.gate.run_commands({"repoRoot": str(self.repo), "commands": list(commands), "env": env or {}})

    def test_a_failing_command_reports_its_exit_code_and_both_streams(self):
        failures, skipped, _, _ = self.run_gate_commands("echo to-stdout; echo to-stderr >&2; exit 3")

        self.assertEqual([], skipped)
        (_command, outcome, output), = failures
        self.assertEqual("exit 3", outcome)
        self.assertIn("to-stdout", output)
        self.assertIn("to-stderr", output)

    def test_the_gate_variables_reach_the_command(self):
        failures, _, _, _ = self.run_gate_commands('test "$GATE_PROBE" = set', env={"GATE_PROBE": "set"})

        self.assertEqual([], failures)

    def test_a_timeout_kills_a_child_that_holds_the_pipes_open(self):
        marker = self.repo / "survived"
        self.gate.COMMAND_TIMEOUT_SECONDS = 1
        started = time.monotonic()

        command = f"echo before; (sleep 3; touch {marker}) & wait"

        failures, _, timed_out, _ = self.run_gate_commands(command)

        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual([], failures)
        (timed_out_command, output, command_timeout), = timed_out
        self.assertEqual(command, timed_out_command)
        self.assertEqual(1, command_timeout)
        self.assertIn("before", output)
        time.sleep(3)
        self.assertFalse(marker.exists())

    def test_a_timed_out_scoped_test_names_the_log_that_keeps_its_output(self):
        log_path = self.repo / "scoped-tests.log"
        command = "echo partial-marker && sleep 30"

        with mock.patch.object(self.gate, "COMMAND_TIMEOUT_SECONDS", 1):
            result, tails = self.gate.run_scoped_tests(str(self.repo), [command], (), log_path)

        self.assertEqual(f"not run (timeout): {command}; full output: {log_path}", result)
        self.assertEqual([], tails)
        log_text = log_path.read_text()
        self.assertIn(f"$ {command}\ntimeout\n", log_text)
        self.assertIn("partial-marker", log_text)

    def test_a_scoped_test_that_names_a_missing_path_is_a_command_error_with_the_log(self):
        log_path = self.repo / "scoped-tests.log"
        message = "ERROR: file or directory not found: missing/test_x.py"
        command = f'echo "{message}"; exit 1'

        result, tails = self.gate.run_scoped_tests(str(self.repo), [command], (), log_path)

        self.assertEqual(f"command error: {command} ({message}); full output: {log_path}", result)
        self.assertEqual([], tails)
        self.assertIn(message, log_path.read_text())


def load_gate_module():
    spec = importlib.util.spec_from_file_location("coder_gate_under_test", GATE_SCRIPT)
    gate_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate_module)
    return gate_module


class CommandCheckScopeTests(unittest.TestCase):
    def setUp(self):
        temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temp_directory.cleanup)
        self.project = pathlib.Path(temp_directory.name)
        self.gate = load_gate_module()

    def write_makefile(self, text, folder="", name="Makefile"):
        makefile_folder = self.project / folder
        makefile_folder.mkdir(parents=True, exist_ok=True)
        (makefile_folder / name).write_text(text)

    def scope(self, command):
        return check_scope.command_check_scope(command, self.project)

    def test_a_direct_command_is_judged_whole_targeted_or_none(self):
        cases = {
            "pytest": "whole",
            "npm run build": "whole",
            "FOO=1 pytest .": "whole",
            "pytest tests/test_x.py": "targeted",
            "jest --onlyChanged": "targeted",
            "git status": "none",
            "pytest 'unclosed": "unresolved",
            "poetry run pytest": "whole",
            "pipenv run pytest": "whole",
            "poetry run pytest tests/test_x.py": "targeted",
            ".venv/bin/python -m pytest": "whole",
            ".venv/bin/python -m pytest tests/test_x.py": "targeted",
            "python manage.py test": "whole",
            "pipenv run python manage.py test": "whole",
            "python manage.py test --noinput": "whole",
            "python manage.py test app.tests": "targeted",
            "python manage.py migrate": "none",
            "python manage.py test -v 2": "whole",
            "python manage.py test --settings x": "whole",
            "./manage.py test": "whole",
            "python backend/manage.py test": "whole",
            "poetry run python backend/manage.py test app.tests": "targeted",
            "python3.12 -m pytest": "whole",
            "uv run pytest": "whole",
            "timeout 60 docker exec c pytest": "whole",
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(expected, self.scope(command))

    def test_a_runner_read_by_its_flags_is_targeted_on_a_name_or_selector_and_none_without(self):
        targeted = (
            "cargo test empty_input", "cargo test tests/foo.rs", "cargo test -p core", "cargo test --package=core",
            "cargo test --test integration", "cargo test --test=integration", "cargo test --bench=parse",
            "cargo test --lib", "cargo test --doc", "cargo test --bins", "cargo nextest run parser",
            "cargo nextest run -E 'test(parser)'", "cargo nextest run -E='test(parser)'",
            "go test -run TestX ./...", "go test -run=TestX ./...", "go test ./pkg/...", "go test .",
            "rspec spec", "rspec -e login", "bundle exec rspec spec/models/user_spec.rb", "mypy src", "pyright src",
            "phpunit tests", "phpunit --filter testLogin", "phpunit --filter=testLogin", "bats -p test/login.bats",
            "docker compose exec web cargo test tests/x.rs", "mypy -p app", "go test -fuzz=FuzzParse",
            "mypy --module=app", "rspec --pattern=spec/models", "rspec --only-failures", "bats --filter=login",
            "cargo nextest run --skip=slow", "cargo nextest run --run-ignored only",
            "cargo nextest run --run-ignored=ignored-only", "cargo nextest run --partition hash:1/2",
            "cargo nextest run --partition=count:1/3", "cargo test -- --ignored", "npx rspec spec", "npx mypy src",
            "bunx mypy src", "phpunit --group=slow", "phpunit --testsuite=unit", "dotnet test --filter=Login",
            "bats --filter-tags=smoke", "rspec --tag=slow", "rspec --example=login", "go test -skip=TestX ./...",
            "mypy --package=app", "cargo nextest run --filterset=test(x)", "cargo test --tests",
            "rspec --next-failure", "cargo test --bin=app", "cargo test --example=demo", "cargo test --examples",
            "cargo test --benches", "cargo nextest run --filter-expr=x", "tsc src/a.ts", "npx tsc src/a.ts",
        )
        whole_runs_read_none = (
            "mypy .", "pyright .", "rspec .", "phpunit .", "bats .", "dotnet test .",
            "cargo test", "cargo nextest run", "cargo +nightly test", "cargo test --manifest-path=/r/a/Cargo.toml",
            "cargo test --target-dir target/x", "cargo test --color always", "cargo clippy --workspace -- -D warnings",
            "go test ./...", "go vet -p 4 ./...",
            "go test -coverprofile cover/c.out ./...", "go build -o bin/app ./...", "go test -mod vendor ./...",
            "tsc -p packages/web/tsconfig.json", "npx tsc --project packages/web/tsconfig.json",
            "tsc -t es2020 --noEmit", "dotnet test --project src/App", "dotnet test --logger trx", "bats -p",
            "rspec --format documentation", "bundle exec rspec --format progress",
            "phpunit --configuration phpunit.xml", "mypy --python-version 3.11", "pyright --pythonversion 3.11",
            "go test -coverpkg ./pkg/... ./...", "go test -bench . ./...", "go test -benchtime 2s -trace t.out ./...",
            "go test -fuzztime 10s ./...", "phpunit -d memory_limit=1G",
            "cargo nextest run --retries 2",
            "phpunit --coverage-clover coverage.xml", "rspec --out results.txt .", "go test -buildmode pie ./...",
            "cargo test --workspace -- --format terse", "cargo test -- --logfile out.txt", "bats -j 4 .",
            "pyright --level error .", "dotnet test --collect \"Code Coverage\"",
            "cargo nextest run --run-ignored all", "cargo nextest run --run-ignored=default",
            "cargo nextest run -P ci", "phpunit --cache-directory .cache", "phpunit --processes 4",
            "phpunit --log-tap out.tap", "rspec --failure-exit-code 2", "rspec --deprecation-out log.txt",
            "rspec -O .rspec-ci", "dotnet test --results-directory out", "dotnet test -e CI=1",
            "dotnet test --blame-hang-timeout 5m", "mypy --always-true DEBUG .",
        )

        for command in targeted:
            with self.subTest(targeted=command):
                self.assertEqual("targeted", self.scope(command))

        # A whole run of these runners stays "none", so the coder gate lets a coder run it.
        for command in whole_runs_read_none:
            with self.subTest(whole=command):
                self.assertEqual("none", self.scope(command))

    def test_a_run_that_excludes_part_of_the_suite_is_targeted(self):
        excluding_runs = (
            "cargo clippy --workspace --exclude foo -- -D warnings", "cargo test --workspace --exclude=foo",
            "cargo nextest run --workspace --exclude foo", "mypy --exclude tests .", "mypy --exclude=tests .",
            "rspec --exclude-pattern spec/slow/**", "rspec --exclude-pattern=spec/slow/**",
            "phpunit --exclude-group slow", "phpunit --exclude-group=slow", "phpunit --exclude-filter=testSlow",
            "phpunit --exclude-testsuite unit", "phpunit --exclude-testsuite=unit", "bats --negative-filter=slow .",
            "python manage.py test --exclude-tag slow", "python manage.py test --exclude-tag=slow",
            "pytest --ignore=tests/slow", "pytest --ignore-glob=tests/slow*", "pytest --deselect=tests/test_a.py::t",
            "npx vitest run --exclude=src/slow", "npx jest --testPathIgnorePatterns=slow",
            "npm test -- --testPathIgnorePatterns=slow", "npm test -- --exclude-tag=slow",
            "yarn test --exclude-tag=slow", "npx eslint --ignore-pattern=src/gen .",
            "npx eslint --ignore-path=.eslintignore .",
            "ruff check --exclude=src/gen", "ruff check --extend-exclude=src/gen",
        )

        for command in excluding_runs:
            with self.subTest(command=command):
                self.assertEqual("targeted", self.scope(command))

    def test_a_run_with_a_flag_that_leaves_nothing_out_is_whole(self):
        whole_runs = (
            "pytest --import-mode=importlib", "npx vitest run --reporter=verbose", "npx eslint --max-warnings=0 .",
            "ruff check --output-format=github", "python manage.py test --settings=x",
            "ruff check --ignore=E501 .",
        )

        for command in whole_runs:
            with self.subTest(command=command):
                self.assertEqual("whole", self.scope(command))

    def test_make_scope_is_read_from_the_makefile(self):
        eight_deep = "".join(f"t{number}: t{number + 1}\n" for number in range(8)) + "t8:\n\tpytest\n"
        cases = [
            ("a runner wrapper is read through",
             {"Makefile": "test:\n\tpytest\n"}, [("poetry run make test", "whole")]),
            ("a recipe that runs the whole suite is whole",
             {"Makefile": "test:\n\tpytest\n"}, [("make test", "whole")]),
            ("a recipe that names a test file is targeted",
             {"Makefile": "test:\n\tpytest tests/test_x.py\n"}, [("make test", "targeted")]),
            ("no target runs the first goal",
             {"Makefile": ".PHONY: test lint\nlint:\n\truff check src\ntest:\n\tpytest\n"}, [("make", "targeted")]),
            ("no target honors the default goal variable",
             {"Makefile": ".DEFAULT_GOAL := test\nlint:\n\truff check src\ntest:\n\tpytest\n"}, [("make", "whole")]),
            ("prerequisites are followed",
             {"Makefile": "check: lint test\nlint:\n\truff check src\ntest:\n\t@pytest\n"}, [("make check", "whole")]),
            ("make recursion in a recipe is followed",
             {"Makefile": "all:\n\t$(MAKE) test\ntest:\n\t-pytest\n"}, [("make all", "whole")]),
            ("prerequisites that form a cycle end", {"Makefile": "a: b\nb: a\n"}, [("make a", "none")]),
            ("recursion deeper than the cap is unresolved", {"Makefile": eight_deep}, [("make t0", "unresolved")]),
            ("the directory option picks the makefile",
             {"sub/Makefile": "test:\n\tpytest\n", "Makefile": "test:\n\tpytest tests/a.py\n"},
             [("make -C sub test", "whole"), ("make --directory=sub test", "whole"), ("cd sub && make test", "whole"),
              ("make test", "targeted")]),
            ("the file option picks the makefile",
             {"ci.mk": "test:\n\tpytest\n", "Makefile": "test:\n\tpytest tests/a.py\n"},
             [("make -f ci.mk test", "whole"), ("make --file=ci.mk test", "whole"), ("make -fci.mk test", "whole")]),
            ("variables in a recipe are expanded",
             {"Makefile": "RUNNER = pytest\nARGS ?=\nBRACED := ${RUNNER}\ntest:\n\t$(RUNNER) $(ARGS)\n"
                          "other:\n\t${BRACED} tests/a.py\n"},
             [("make test", "whole"), ("make other", "targeted")]),
            ("a recipe continued over lines is joined",
             {"Makefile": "test:\n\tpytest \\\n\t  tests/test_x.py\n"}, [("make test", "targeted")]),
            ("a variable argument is let through",
             {"Makefile": "test:\n\tpytest $(FILE)\n"}, [("make test FILE=tests/test_x.py", "unresolved")]),
            ("a variable assignment before make is let through",
             {"Makefile": "test:\n\tpytest $(TESTS)\n"}, [("TESTS=tests/a.py make test", "unresolved")]),
            ("order-only prerequisites are followed",
             {"Makefile": "check: lint | test\nlint:\n\truff check tests/a.py\ntest:\n\tpytest\n"},
             [("make check", "whole")]),
            ("order-only prerequisites alone are followed",
             {"Makefile": "check: | test\ntest:\n\tpytest\n"}, [("make check", "whole")]),
            ("recipe lines inside a define block belong to no rule",
             {"Makefile": "test:\n\tpytest tests/a.py\ndefine HELP\n\tpytest\nendef\n"}, [("make test", "targeted")]),
            ("a target whose chain ran past the depth cap is read again by a shorter path",
             {"Makefile": "check: p test\np: q\nq: test\ntest: u\nu: v\nv:\n\tpytest\n"}, [("make check", "whole")]),
            ("recursion into another directory reads that directory's makefile",
             {"Makefile": "test:\n\tpytest tests/a.py\nall:\n\t$(MAKE) -C sub test\n",
              "sub/Makefile": "test:\n\tpytest\n"}, [("make all", "whole")]),
            ("recursion inside another directory reads that directory's makefile",
             {"Makefile": "test:\n\tpytest tests/a.py\n",
              "sub/Makefile": "all:\n\t$(MAKE) test\ntest:\n\tpytest\n"}, [("make -C sub all", "whole")]),
            ("no makefile is let through", {}, [("make test", "unresolved")]),
            ("no such target is let through", {"Makefile": "lint:\n\truff check src\n"},
             [("make test", "unresolved")]),
            ("a whole recipe command beats an unresolved one",
             {"Makefile": "test:\n\tpytest\n"}, [("make missing test", "whole")]),
            ("a recipe that runs through docker is judged by the command inside",
             {"Makefile": "test:\n\t@docker compose run --rm app npm test\n"}, [("make test", "whole")]),
        ]
        for label, makefiles, commands in cases:
            with self.subTest(label):
                for path, text in makefiles.items():
                    folder, _, name = path.rpartition("/")
                    self.write_makefile(text, folder=folder, name=name)
                for command, expected in commands:
                    self.assertEqual(expected, self.scope(command), command)
                for path in makefiles:
                    (self.project / path).unlink()

    def test_an_assignment_dropped_by_a_wrapper_lets_make_through_and_a_wrapper_inside_docker_is_peeled(self):
        self.write_makefile("test:\n\tnpm test\n")
        cases = {
            "env TESTS=a make test": "unresolved",
            "TESTS=a make test": "unresolved",
            "docker exec x timeout 60 make test": "whole",
            "docker exec x env TESTS=a make test": "unresolved",
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(expected, self.scope(command))

    def test_an_assignment_before_a_docker_call_lets_the_inner_make_through_only_when_the_call_forwards_it(self):
        self.write_makefile("test:\n\tpytest\n")
        cases = {
            "COMPOSE_PROJECT_NAME=x docker compose exec app make test": "whole",
            "FILE=x docker compose exec -e OTHER app make test": "whole",
            "FILE=x docker compose exec -e FILE=y app make test": "unresolved",
            "docker compose exec -e FILE=tests/a.py app make test": "unresolved",
            "FILE=x docker compose exec -e FILE app make test": "unresolved",
            "FILE=x docker compose run --rm --env FILE app make test": "unresolved",
            "FILE=x docker exec --env=FILE app make test": "unresolved",
            "FILE=x docker exec -eFILE app make test": "unresolved",
            "A=1 FILE=x docker compose exec -e FILE app make test": "unresolved",
            "FILE=x docker compose exec -e FILE app pytest": "whole",
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(expected, self.scope(command))

    def test_make_that_runs_no_recipe_is_none(self):
        self.write_makefile("test:\n\tpytest\n")
        options = ("-n", "--dry-run", "--just-print", "--recon", "-q", "--question", "--help", "-h", "-t", "--touch",
                   "-nk", "-sn")
        for option in options:
            with self.subTest(option=option):
                self.assertEqual("none", self.scope(f"make {option} test"))
        self.assertEqual("none", self.scope("make -n test FILE=x"))
        self.assertEqual("none", self.scope("docker compose exec app make -n test"))
        self.assertEqual("whole", self.scope("make -s -j4 test"))

    def test_make_that_prints_the_data_base_or_sets_output_sync_still_runs_the_recipe(self):
        self.write_makefile("test:\n\tpytest\n")

        for option in ("-p", "--print-data-base", "-Onone", "-O"):
            with self.subTest(option=option):
                self.assertEqual("whole", self.scope(f"make {option} test"))

    def test_a_recipe_after_an_include_export_define_or_vpath_line_still_belongs_to_its_rule(self):
        lines_before_the_recipe = {
            "include": "include other.mk",
            "dash include": "-include other.mk",
            "sinclude": "sinclude other.mk",
            "export with assignment": "export FOO = 1",
            "export without assignment": "export FOO",
            "unexport": "unexport FOO",
            "vpath": "vpath %.c src",
            "define block": "define HELP\nTHE TEXT\n\tnot a recipe\nA = 1\nendef",
            "nested define block": "define OUTER\ndefine INNER\nx\nendef\ny\nendef",
            "exported define block": "export define HELP\nx\nendef",
        }
        for name, line in lines_before_the_recipe.items():
            with self.subTest(name=name):
                self.write_makefile(f"test:\n{line}\n\tpytest\n")

                self.assertEqual("whole", self.scope("make test"))

    def test_docker_exec_and_run_are_judged_by_the_command_inside(self):
        cases = {
            "docker compose exec -T app pytest": "whole",
            "docker-compose run --rm -e A=1 app pytest": "whole",
            "docker exec -it -w /app web npm test": "whole",
            "docker run --rm --name x -v /a:/b image pytest": "whole",
            "docker run --memory 1g --cpus 2 app pytest": "whole",
            "docker compose exec app pytest tests/test_x.py": "targeted",
            "docker compose exec app ls": "none",
            "docker compose up -d": "none",
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(expected, self.scope(command))

    def test_the_refusal_text_shows_the_recipe_command_and_the_make_call_as_written(self):
        self.write_makefile("test:\n\tPYTHONPATH=. pytest\n")

        recipe_reason = self.gate.whole_package_reason("make test", self.project)
        docker_reason = self.gate.whole_package_reason("docker compose exec app make test", self.project)

        self.assertIn("`make test` runs `PYTHONPATH=. pytest` in target `test`", recipe_reason)
        self.assertIn("`docker compose exec app make test` runs `PYTHONPATH=. pytest` in target `test`", docker_reason)

    def test_the_bash_hook_names_the_target_and_recipe_command_it_refuses(self):
        self.write_makefile("test:\n\t@docker compose exec -T app pytest\n")
        environment = {**os.environ, "CLAUDE_TOOLKIT_TELEMETRY": "0"}
        event = {"agent_type": "coder", "cwd": str(self.project), "tool_input": {"command": "make test"}}

        done = subprocess.run([sys.executable, "-B", str(GATE_SCRIPT), "bash-hook"], input=json.dumps(event),
                              env=environment, capture_output=True, text=True)

        decision = json.loads(done.stdout)["hookSpecificOutput"]
        self.assertEqual("deny", decision["permissionDecision"])
        reason = decision["permissionDecisionReason"]
        self.assertIn("`make test` runs `docker compose exec -T app pytest` in target `test`", reason)
        self.assertIn("targeted command", reason)

    def test_the_bash_hook_lets_a_targeted_make_target_through(self):
        self.write_makefile("test:\n\tpytest tests/test_x.py\n")
        environment = {**os.environ, "CLAUDE_TOOLKIT_TELEMETRY": "0"}
        event = {"agent_type": "coder", "cwd": str(self.project), "tool_input": {"command": "make test"}}

        done = subprocess.run([sys.executable, "-B", str(GATE_SCRIPT), "bash-hook"], input=json.dumps(event),
                              env=environment, capture_output=True, text=True)

        self.assertEqual("", done.stdout)
        self.assertEqual(0, done.returncode)
        self.assertEqual("", done.stderr)


if __name__ == "__main__":
    unittest.main()
