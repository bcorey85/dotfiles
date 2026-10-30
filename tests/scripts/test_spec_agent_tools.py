"""Checks that each spec agent that writes a file also has Edit, so it can correct that file without a shell rewrite,
and that goal-blind research keeps the ticket out of its searches."""
import re
import unittest

import toolkit_paths

SPEC_AGENTS_THAT_WRITE = ["spec-questions", "spec-research", "spec-criteria"]
RESEARCH_CHILDREN = ["spec-questions", "spec-research"]


def agent_text(agent_name):
    return (toolkit_paths.CLAUDE_DIR / "agents" / f"{agent_name}.md").read_text()


def agent_tools(agent_name):
    tools_line = re.search(r"^tools:\s*(.+)$", agent_text(agent_name), re.MULTILINE)
    return [tool.strip() for tool in tools_line.group(1).split(",")]


class SpecAgentToolsTest(unittest.TestCase):
    def test_every_spec_agent_that_writes_a_file_can_also_edit_it(self):
        for agent_name in SPEC_AGENTS_THAT_WRITE:
            with self.subTest(agent=agent_name):
                tools = agent_tools(agent_name)
                self.assertIn("Write", tools)
                self.assertIn("Edit", tools)

    def test_research_children_are_told_to_edit_with_edit_not_sed(self):
        for agent_name in RESEARCH_CHILDREN:
            with self.subTest(agent=agent_name):
                self.assertIn("never `sed -i`", agent_text(agent_name))


class GoalBlindTicketExcludeTest(unittest.TestCase):
    def test_goal_blind_researcher_hands_spec_research_an_exclude_glob(self):
        researcher = " ".join(agent_text("goal-blind-researcher").split())

        self.assertIn("exclude: !{docs/plans/<slug>/**,<source ticket folder>/**}", researcher)
        self.assertIn("Name the folder, never the file", researcher)
        self.assertIn("exclude: !{docs/plans/<slug>/**}", researcher)

    def test_spec_research_applies_the_exclude_glob_to_every_search(self):
        research = " ".join(agent_text("spec-research").split())

        self.assertIn("a questions path, an `exclude:` line and a target directory", research)
        self.assertIn("Search file contents only with `rg` in Bash", research)
        self.assertIn("Add `--glob '<the glob>'` to every `rg` in Bash", research)
        self.assertIn("filter by file type with `-t`, never a second glob", research)
        self.assertNotIn("Grep", agent_tools("spec-research"))
        self.assertNotIn("Glob", agent_tools("spec-research"))
        self.assertIn("Bash", agent_tools("spec-research"))
        self.assertIn("Never search file contents with `grep -r`, `find -exec` or `git grep`", research)
        self.assertIn("never `cd` before a search", research)

    def test_eng_spec_forwards_the_source_ticket_file(self):
        phase_file = toolkit_paths.CLAUDE_DIR / "skills" / "eng-spec" / "phases" / "2-research.md"
        phase_text = " ".join(phase_file.read_text().split())

        self.assertIn("pass that source ticket file's path relative to the session working directory", phase_text)


if __name__ == "__main__":
    unittest.main()
