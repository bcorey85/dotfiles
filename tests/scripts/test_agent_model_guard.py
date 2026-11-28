"""Checks for agent-model-guard.sh, the PreToolUse hook that denies an Agent call that would inherit the Opus model.

Set AGENT_MODEL_GUARD to run against another copy of the script."""
import json
import os
import pathlib
import subprocess
import tempfile
import unittest

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("AGENT_MODEL_GUARD") or toolkit_paths.SCRIPTS_DIR / "agent-model-guard.sh")


def write_agent_files(root, agent_files):
    """Write each {name: text} pair to <root>/.claude/agents/<name>.md."""
    agents_dir = pathlib.Path(root) / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    for name, text in agent_files.items():
        (agents_dir / f"{name}.md").write_text(text)


def run_guard(tool_input, home_agents=None, project_agents=None, tool_name="Agent", extra_environment=None):
    """Run the hook on a tool call (an Agent call by default).
    By default the home is empty, so no agent file pins a model.
    home_agents and project_agents map an agent name to its file text; project_agents sets CLAUDE_PROJECT_DIR.
    extra_environment adds variables to the hook's environment.
    Returns (exit code, parsed stdout JSON or None)."""
    event = {"tool_name": tool_name, "tool_input": tool_input}
    with tempfile.TemporaryDirectory() as scratch:
        environment = {key: value for key, value in os.environ.items()
                       if key not in ("CLAUDE_SKIP_HOOKS", "CLAUDE_PROJECT_DIR")}
        environment.update(extra_environment or {})
        home = pathlib.Path(scratch) / "home"
        home.mkdir()
        environment["HOME"] = str(home)
        write_agent_files(home, home_agents or {})
        if project_agents is not None:
            project = pathlib.Path(scratch) / "project"
            project.mkdir()
            write_agent_files(project, project_agents)
            environment["CLAUDE_PROJECT_DIR"] = str(project)
        finished = subprocess.run(["bash", str(SCRIPT)], input=json.dumps(event), capture_output=True,
                                  text=True, env=environment)
    reply = json.loads(finished.stdout) if finished.stdout.strip() else None
    return finished.returncode, reply


def denial_reason(reply):
    if reply is None:
        return None
    output = reply["hookSpecificOutput"]
    if output["permissionDecision"] != "deny":
        return None
    return output["permissionDecisionReason"]


class AgentModelGuardTest(unittest.TestCase):
    def test_fork_without_model_passes(self):
        code, reply = run_guard({"subagent_type": "fork", "prompt": "carry on"})
        self.assertEqual(code, 0)
        self.assertIsNone(reply, "a fork runs on the parent model, so the guard prints no deny")

    def test_fork_with_opus_model_passes(self):
        code, reply = run_guard({"subagent_type": "fork", "model": "opus", "prompt": "x"})
        self.assertEqual(code, 0)
        self.assertIsNone(reply, "the harness ignores a model on a fork, so the fork check precedes the opus check")

    def test_fork_with_inherit_model_passes(self):
        code, reply = run_guard({"subagent_type": "fork", "model": "inherit", "prompt": "x"})
        self.assertEqual(code, 0)
        self.assertIsNone(reply, "the harness ignores a model on a fork, so the fork check precedes the inherit check")

    def test_unpinned_agent_without_file_is_denied(self):
        code, reply = run_guard({"subagent_type": "no-such-agent", "prompt": "x"})
        self.assertEqual(code, 0)
        self.assertIn("no model pin", denial_reason(reply) or "")

    def test_forker_without_model_or_agent_file_is_denied(self):
        code, reply = run_guard({"subagent_type": "forker", "prompt": "x"})
        self.assertEqual(code, 0)
        self.assertIn("no model pin", denial_reason(reply) or "", "only the exact name fork is exempt")

    def test_agent_with_model_frontmatter_pin_passes(self):
        code, reply = run_guard({"subagent_type": "pinned", "prompt": "x"},
                                home_agents={"pinned": "---\nmodel: sonnet\n---\nbody\n"})
        self.assertEqual(code, 0)
        self.assertIsNone(reply, "a model: frontmatter line selects the model, so the guard prints no deny")

    def test_project_agent_file_is_preferred_over_home(self):
        code, reply = run_guard({"subagent_type": "pinned", "prompt": "x"},
                                home_agents={"pinned": "---\nname: pinned\n---\n"},
                                project_agents={"pinned": "---\nmodel: sonnet\n---\n"})
        self.assertEqual(code, 0)
        self.assertIsNone(reply, "the pinned project file wins over the unpinned home file")

    def test_invalid_subagent_type_is_denied(self):
        code, reply = run_guard({"subagent_type": "../../etc/x", "prompt": "x"})
        self.assertEqual(code, 0)
        self.assertIn("invalid", denial_reason(reply) or "")

    def test_explicit_non_opus_model_passes(self):
        code, reply = run_guard({"subagent_type": "no-such-agent", "model": "sonnet", "prompt": "x"})
        self.assertEqual(code, 0)
        self.assertIsNone(reply, "an explicit non-opus model needs no agent file pin")

    def test_opus_on_non_fork_agent_is_denied(self):
        code, reply = run_guard({"subagent_type": "no-such-agent", "model": "opus", "prompt": "x"})
        self.assertEqual(code, 0)
        self.assertIn("opus", denial_reason(reply) or "")

    def test_inherit_on_non_fork_agent_is_denied(self):
        code, reply = run_guard({"subagent_type": "no-such-agent", "model": "inherit", "prompt": "x"})
        self.assertEqual(code, 0)
        self.assertIn("inherit", denial_reason(reply) or "")

    def test_every_denial_opens_with_the_guard_tag(self):
        cases = [{"subagent_type": "../../etc/x"}, {"subagent_type": "no-such-agent", "model": "opus"},
                 {"subagent_type": "no-such-agent", "model": "inherit"}, {"subagent_type": "no-such-agent"}]
        for tool_input in cases:
            with self.subTest(tool_input=tool_input):
                code, reply = run_guard({**tool_input, "prompt": "x"})
                self.assertEqual(code, 0)
                self.assertTrue((denial_reason(reply) or "").startswith("[agent-model-guard] "))

    def test_skip_hooks_variable_passes_opus(self):
        code, reply = run_guard({"subagent_type": "no-such-agent", "model": "opus", "prompt": "x"},
                                extra_environment={"CLAUDE_SKIP_HOOKS": "1"})
        self.assertEqual(code, 0)
        self.assertIsNone(reply, "CLAUDE_SKIP_HOOKS bypasses the guard, so an opus model prints no deny")

    def test_non_agent_tool_without_model_passes(self):
        code, reply = run_guard({"command": "ls"}, tool_name="Bash")
        self.assertEqual(code, 0)
        self.assertIsNone(reply, "the guard only checks Agent calls")

    def test_opus_match_ignores_case(self):
        code, reply = run_guard({"subagent_type": "no-such-agent", "model": "OPUS", "prompt": "x"})
        self.assertEqual(code, 0)
        self.assertIn("opus", denial_reason(reply) or "")

    def test_inherit_match_ignores_case(self):
        code, reply = run_guard({"subagent_type": "no-such-agent", "model": "Inherit", "prompt": "x"})
        self.assertEqual(code, 0)
        self.assertIn("inherit", denial_reason(reply) or "")

    def test_unpinned_web_fetch_runs_pinned_to_haiku(self):
        code, reply = run_guard({"subagent_type": "web-fetch", "prompt": "read https://example.com"})
        self.assertEqual(code, 0)
        self.assertIsNotNone(reply, "an unpinned web-fetch call gets a rewrite, not silence")
        assert reply is not None
        output = reply["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "allow")
        self.assertEqual(output["updatedInput"],
                         {"subagent_type": "web-fetch", "prompt": "read https://example.com", "model": "haiku"},
                         "the rewrite adds the haiku pin and keeps every other field")

    def test_web_fetch_with_explicit_sonnet_is_left_alone(self):
        code, reply = run_guard({"subagent_type": "web-fetch", "model": "sonnet", "prompt": "x"})
        self.assertEqual(code, 0)
        self.assertIsNone(reply, "a pinned web-fetch call keeps its own model")

    def test_web_fetch_with_opus_is_denied(self):
        code, reply = run_guard({"subagent_type": "web-fetch", "model": "opus", "prompt": "x"})
        self.assertEqual(code, 0)
        self.assertIn("opus", denial_reason(reply) or "")

    def test_web_fetch_with_inherit_is_denied(self):
        code, reply = run_guard({"subagent_type": "web-fetch", "model": "inherit", "prompt": "x"})
        self.assertEqual(code, 0)
        self.assertIn("inherit", denial_reason(reply) or "")

    def test_unpinned_general_purpose_is_still_denied(self):
        code, reply = run_guard({"subagent_type": "general-purpose", "prompt": "x"})
        self.assertEqual(code, 0)
        self.assertIn("no model pin", denial_reason(reply) or "", "only web-fetch gets the haiku rewrite")


if __name__ == "__main__":
    unittest.main()
