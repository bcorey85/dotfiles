"""Checks that each spec agent that writes a file also has Edit, so it can correct that file without a shell rewrite."""
import re
import unittest

import toolkit_paths

SPEC_AGENTS_THAT_WRITE = ["spec-questions", "spec-research", "spec-criteria"]


def agent_tools(agent_name):
    agent_file = toolkit_paths.CLAUDE_DIR / "agents" / f"{agent_name}.md"
    tools_line = re.search(r"^tools:\s*(.+)$", agent_file.read_text(), re.MULTILINE)
    return [tool.strip() for tool in tools_line.group(1).split(",")]


class SpecAgentToolsTest(unittest.TestCase):
    def test_every_spec_agent_that_writes_a_file_can_also_edit_it(self):
        for agent_name in SPEC_AGENTS_THAT_WRITE:
            with self.subTest(agent=agent_name):
                tools = agent_tools(agent_name)
                self.assertIn("Write", tools)
                self.assertIn("Edit", tools)


if __name__ == "__main__":
    unittest.main()
