"""Checks which agent-model guard settings.json registers on PreToolUse(Agent)."""
import json
import unittest

import toolkit_paths

SETTINGS = toolkit_paths.CLAUDE_DIR / "settings.json"
WORK_GUARD = "~/.claude/scripts/agent-model-guard.sh"


def agent_pretooluse_commands():
    settings = json.loads(SETTINGS.read_text())
    commands = []
    for group in settings["hooks"]["PreToolUse"]:
        if group.get("matcher") != "Agent":
            continue
        commands.extend(handler.get("command", "") for handler in group.get("hooks", []))
    return commands


class AgentHookRegistrationTest(unittest.TestCase):
    def test_exactly_one_agent_model_guard_runs_on_agent(self):
        guard_commands = [command for command in agent_pretooluse_commands()
                          if "agent-model-guard" in command or "agent_model_guard" in command]

        self.assertEqual(guard_commands, [WORK_GUARD])


if __name__ == "__main__":
    unittest.main()
