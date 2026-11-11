"""Checks for fork_write_scope.py: code-fork may Write its run folder files, and nothing else."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

HOOK = pathlib.Path(os.environ.get("FORK_WRITE_SCOPE") or toolkit_paths.GATES_DIR / "fork_write_scope.py")
SETTINGS = toolkit_paths.CLAUDE_DIR / "settings.json"
FORK_AGENT = toolkit_paths.CLAUDE_DIR / "agents" / "code-fork.md"


def run_hook(file_path, agent_type="code-fork"):
    payload = {"tool_name": "Write", "tool_input": {"file_path": file_path, "content": "python3 - <<'EOF'\n"}}
    if agent_type:
        payload["agent_type"] = agent_type
    env = {key: value for key, value in os.environ.items() if key != "CLAUDE_SKIP_HOOKS"}
    result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), text=True,
                            capture_output=True, env=env, check=False)
    return result


def decision(result):
    if not result.stdout.strip():
        return "allow"
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]


class ForkWriteScopeTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.repo = pathlib.Path(temp_dir.name) / "repo"
        git_dir = self.repo / ".git"
        (git_dir / "code-phase").mkdir(parents=True)
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
        worktree_git_dir = git_dir / "worktrees" / "lane"
        (worktree_git_dir / "code-phase").mkdir(parents=True)
        (worktree_git_dir / "HEAD").write_text("ref: refs/heads/lane\n")
        self.worktree_run_folder = worktree_git_dir / "code-phase"

    def test_fork_writes_stop_md_in_the_run_folder(self):
        result = run_hook(str(self.repo / ".git" / "code-phase" / "stop.md"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(decision(result), "allow")

    def test_fork_writes_in_a_linked_worktree_run_folder(self):
        result = run_hook(str(self.worktree_run_folder / "review-stop.md"))
        self.assertEqual(decision(result), "allow")

    def test_fork_write_to_a_repo_file_is_denied(self):
        result = run_hook(str(self.repo / "src" / "app.py"))
        self.assertEqual(decision(result), "deny")
        self.assertIn("coder", result.stdout)

    def test_code_phase_folder_outside_a_git_dir_is_denied(self):
        result = run_hook(str(self.repo / "code-phase" / "stop.md"))
        self.assertEqual(decision(result), "deny")

    def test_path_climbing_out_of_the_run_folder_is_denied(self):
        result = run_hook(str(self.repo / ".git" / "code-phase" / ".." / ".." / "app.py"))
        self.assertEqual(decision(result), "deny")

    def test_other_agents_and_the_main_session_pass(self):
        for agent_type in ("coder", None):
            with self.subTest(agent_type=agent_type):
                self.assertEqual(decision(run_hook(str(self.repo / "app.py"), agent_type)), "allow")


class PendingLaunchTest(unittest.TestCase):
    LAUNCH_LINE = "python3 ~/.claude/scripts/review/review_fix.py launch --fix /g/review-fix/ask-findings.md --detach"

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        git_dir = pathlib.Path(temp_dir.name) / "repo" / ".git"
        (git_dir / "code-phase").mkdir(parents=True)
        (git_dir / "review-fix").mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
        self.stop_file = str(git_dir / "code-phase" / "review-stop.md")
        self.other_file = str(git_dir / "code-phase" / "stop.md")
        self.state_file = git_dir / "review-fix" / "state.json"

    def test_review_stop_is_denied_while_a_fix_run_is_pending_and_the_reason_names_the_line(self):
        self.state_file.write_text(json.dumps({"asks_launch_pending": self.LAUNCH_LINE}))
        result = run_hook(self.stop_file)
        self.assertEqual(decision(result), "deny")
        reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn(self.LAUNCH_LINE, reason)
        self.assertIn("stop and tell the user", reason)
        self.assertIn("`asks_launch_pending` key", reason)
        self.assertIn(str(self.state_file.resolve()), reason)
        self.assertNotIn("launch a new review", reason)

    def test_review_stop_in_a_linked_worktree_is_denied_while_a_fix_run_is_pending(self):
        worktree_git_dir = self.state_file.parent.parent / "worktrees" / "x"
        (worktree_git_dir / "code-phase").mkdir(parents=True)
        (worktree_git_dir / "review-fix").mkdir()
        (worktree_git_dir / "HEAD").write_text("ref: refs/heads/x\n")
        (worktree_git_dir / "review-fix" / "state.json").write_text(
            json.dumps({"asks_launch_pending": self.LAUNCH_LINE}))
        result = run_hook(str(worktree_git_dir / "code-phase" / "review-stop.md"))
        self.assertEqual(decision(result), "deny")
        self.assertIn(self.LAUNCH_LINE, result.stdout)

    def test_review_stop_is_allowed_without_a_pending_fix_run(self):
        cases = {"no state file": None, "no flag": {"stage": "done"}, "empty flag": {"asks_launch_pending": ""}}
        for label, state in cases.items():
            with self.subTest(label):
                self.state_file.unlink(missing_ok=True)
                if state is not None:
                    self.state_file.write_text(json.dumps(state))
                self.assertEqual(decision(run_hook(self.stop_file)), "allow", label)

    def test_another_run_folder_file_is_allowed_while_a_fix_run_is_pending(self):
        self.state_file.write_text(json.dumps({"asks_launch_pending": self.LAUNCH_LINE}))
        self.assertEqual(decision(run_hook(self.other_file)), "allow")

    def test_a_non_code_fork_write_is_allowed_while_a_fix_run_is_pending(self):
        self.state_file.write_text(json.dumps({"asks_launch_pending": self.LAUNCH_LINE}))
        for agent_type in ("coder", None):
            with self.subTest(agent_type=agent_type):
                self.assertEqual(decision(run_hook(self.stop_file, agent_type)), "allow")

    def test_an_unreadable_state_denies_review_stop_and_names_the_gate(self):
        self.state_file.write_text("{not json")
        result = run_hook(self.stop_file)
        self.assertEqual(decision(result), "deny")
        self.assertIn("fork_write_scope", result.stdout)
        self.assertIn(str(self.state_file.resolve()), result.stdout)
        self.assertIn("Tell the user to repair or delete that file", result.stdout)

    def test_a_state_that_is_not_an_object_denies_review_stop_and_names_the_file(self):
        self.state_file.write_text("[1]")
        result = run_hook(self.stop_file)
        self.assertEqual(decision(result), "deny")
        self.assertIn(str(self.state_file.resolve()), result.stdout)


class ForkHasWriteTest(unittest.TestCase):
    def test_code_fork_may_use_write(self):
        frontmatter = FORK_AGENT.read_text().split("---")[1]
        disallowed_line = next(line for line in frontmatter.splitlines() if line.startswith("disallowedTools:"))
        disallowed = [tool.strip() for tool in disallowed_line.split(":", 1)[1].split(",")]
        self.assertNotIn("Write", disallowed)
        self.assertIn("Edit", disallowed)

    def test_hook_is_registered_on_write(self):
        settings = json.loads(SETTINGS.read_text())
        commands = [hook["command"] for group in settings["hooks"]["PreToolUse"]
                    if group.get("matcher") == "Write" for hook in group.get("hooks", [])]
        self.assertTrue(any("gates/fork_write_scope.py" in command for command in commands), commands)


if __name__ == "__main__":
    unittest.main()
