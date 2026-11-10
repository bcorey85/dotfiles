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
