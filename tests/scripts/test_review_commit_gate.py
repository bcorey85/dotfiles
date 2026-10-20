"""Checks for review-commit-gate.py: a coder dispatch obligates /review before a commit."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR")
                      or pathlib.Path.home() / ".claude" / "scripts") / "review-commit-gate.py"
ASK = ("[review-commit-gate] Coder work from this session has no converged /review. Allow to commit anyway, or "
       "deny and run /review.")


class ReviewCommitGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.state_dir = self.home / ".claude" / "state" / "review-gate"

    def fire_raw(self, stdin, env_extra=None):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home), "TMPDIR": str(self.tmp)}
        env.update(env_extra or {})
        return subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True, env=env,
                              cwd=str(self.tmp))

    def dispatch(self, subagent="coder", session="s1", **extra):
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Agent", "session_id": session,
                   "tool_input": {"subagent_type": subagent}}
        payload.update(extra)
        return self.fire_raw(json.dumps(payload))

    def bash(self, command, session="s1", **extra):
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": session,
                   "tool_input": {"command": command}}
        payload.update(extra)
        return self.fire_raw(json.dumps(payload))

    def assert_silent(self, finished):
        self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, "", ""))

    def assert_asks(self, finished, reason=ASK, stderr=""):
        self.assertEqual(finished.returncode, 0)
        self.assertEqual(finished.stderr, stderr)
        self.assertEqual(json.loads(finished.stdout), {"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": reason}})

    def state(self, session="s1"):
        path = self.state_dir / session
        return path.read_text() if path.exists() else None

    def test_commit_without_coder_dispatch_passes(self):
        self.assert_silent(self.bash("git commit -m x"))

    def test_coder_dispatch_makes_commit_ask(self):
        self.assert_silent(self.dispatch("coder"))
        self.assertEqual(self.state(), "dirty\n")
        self.assert_asks(self.bash("git commit -m x"))
        self.assert_asks(self.bash("git add . && git  commit -am x"))

    def test_every_coder_variant_marks_dirty(self):
        for name in ("coder", "coder-deep", "backend-coder", "backend-coder-deep", "frontend-coder",
                     "frontend-coder-deep"):
            self.assert_silent(self.dispatch(name, session="v-" + name))
            self.assertEqual(self.state("v-" + name), "dirty\n", name)

    def test_other_agents_do_not_mark_dirty(self):
        for name in ("code-reviewer", "Explore", "coder-lite", "", "mycoder"):
            self.assert_silent(self.dispatch(name))
        self.assertIsNone(self.state())
        self.assert_silent(self.bash("git commit -m x"))

    def test_non_commit_commands_pass_while_dirty(self):
        self.dispatch()
        for command in ("git status", "echo git commits", "ls"):
            self.assert_silent(self.bash(command))

    def test_commit_tree_counts_as_a_commit_like_the_bash_original(self):
        self.dispatch()
        self.assert_asks(self.bash("git commit-tree abc"))

    def test_mark_clean_then_commit_passes_and_mark_dirty_asks_again(self):
        self.dispatch()
        self.assert_silent(self.bash("review-gate-mark clean"))
        self.assertEqual(self.state(), "clean\n")
        self.assert_silent(self.bash("git commit -m x"))
        self.assert_silent(self.bash("~/.claude/scripts/review-gate-mark   dirty"))
        self.assertEqual(self.state(), "dirty\n")
        self.assert_asks(self.bash("git commit -m x"))

    def test_mark_with_other_word_is_ignored(self):
        self.assert_silent(self.bash("review-gate-mark other"))
        self.assertIsNone(self.state())

    def test_commit_beats_mark_in_the_same_command(self):
        self.dispatch()
        self.assert_asks(self.bash("review-gate-mark clean && git commit -m x"))
        self.assertEqual(self.state(), "dirty\n")

    def test_mark_clean_without_prior_state_creates_it(self):
        self.assert_silent(self.bash("review-gate-mark clean"))
        self.assertEqual(self.state(), "clean\n")

    def test_sessions_are_separate_and_missing_session_is_unknown(self):
        self.dispatch(session="a")
        self.assert_asks(self.bash("git commit -m x", session="a"))
        self.assert_silent(self.bash("git commit -m x", session="b"))
        payload = {"hook_event_name": "PostToolUse", "tool_input": {"subagent_type": "coder"}}
        self.fire_raw(json.dumps(payload))
        self.assertEqual(self.state("unknown"), "dirty\n")

    def test_old_state_files_are_pruned(self):
        self.state_dir.mkdir(parents=True)
        old = self.state_dir / "stale"
        old.write_text("dirty\n")
        stale = time.time() - 5 * 86400
        os.utime(str(old), (stale, stale))
        fresh = self.state_dir / "fresh"
        fresh.write_text("dirty\n")
        self.assert_silent(self.bash("ls"))
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())

    def test_unrelated_events_pass(self):
        self.assert_silent(self.fire_raw(json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                                                     "session_id": "s1", "tool_input": {"command": "ls"}})))
        self.assert_silent(self.fire_raw(json.dumps({"hook_event_name": "Stop", "session_id": "s1"})))
        self.assert_silent(self.fire_raw(json.dumps({"hook_event_name": "PreToolUse", "tool_input": {}})))

    def test_skip_hooks_env_passes_and_writes_nothing(self):
        finished = self.fire_raw(json.dumps({"hook_event_name": "PostToolUse", "session_id": "s1",
                                             "tool_input": {"subagent_type": "coder"}}),
                                 env_extra={"CLAUDE_SKIP_HOOKS": "1"})
        self.assert_silent(finished)
        self.assertFalse(self.state_dir.exists())

    def test_unparseable_input_asks_with_internal_error(self):
        self.assert_asks(self.fire_raw("not json"),
                         "[review-commit-gate] internal error (exit 2). Allow to run the command anyway.")

    def test_internal_error_asks_on_pre_but_stays_silent_on_post(self):
        (self.home / ".claude").write_text("a file, not a directory")
        self.assert_asks(self.bash("git commit -m x"),
                         "[review-commit-gate] internal error (exit 1). Allow to run the command anyway.",
                         stderr="mkdir: cannot create directory '%s': Not a directory\n" % (self.home / ".claude"))
        finished = self.dispatch()
        self.assertEqual((finished.returncode, finished.stdout), (1, ""))

    def test_string_tool_input_asks_with_jq_error_code(self):
        payload = {"hook_event_name": "PreToolUse", "session_id": "s1", "tool_input": "oops"}
        self.assert_asks(self.fire_raw(json.dumps(payload)),
                         "[review-commit-gate] internal error (exit 5). Allow to run the command anyway.")

    def test_empty_input_passes_and_creates_state_dir(self):
        self.assert_silent(self.fire_raw(""))
        self.assertTrue(self.state_dir.is_dir())


if __name__ == "__main__":
    unittest.main()
