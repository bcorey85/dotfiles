"""The lane brief template: a forked lane reads its rules from one toolkit file, and the orchestration rules point
every lane brief at it."""
import unittest

import toolkit_paths

LANE_BRIEF_FILE = toolkit_paths.CLAUDE_DIR / "skills" / "_shared" / "lane-brief.md"
ORCHESTRATION_FILE = toolkit_paths.CLAUDE_DIR / "orchestration.md"
RULE_HEADINGS = (
    "## Report only to the orchestrator",
    "## Run every phase through",
    "## Record rulings",
    "## Toolkit edits",
    "## Checks under the memory cap",
    "## Final report",
)


class LaneBriefTest(unittest.TestCase):
    def test_the_template_names_each_lane_rule_heading(self):
        text = LANE_BRIEF_FILE.read_text()
        for heading in RULE_HEADINGS:
            with self.subTest(heading=heading):
                self.assertIn(f"\n{heading}\n", text)

    def test_the_ruling_form_matches_the_standing_ruling_reader(self):
        text = LANE_BRIEF_FILE.read_text()
        self.assertIn("`Standing ruling by <who> at <YYYY-MM-DD>: ", text)
        self.assertIn(" covers: rewords`", text)

    def test_the_lane_start_rule_names_the_brief_file_form_and_the_template(self):
        text = ORCHESTRATION_FILE.read_text()
        start_line = next((line for line in text.splitlines() if "herdr-worktree --prompt-file" in line), "")
        self.assertTrue(start_line, "orchestration.md has no lane-start line naming herdr-worktree --prompt-file")
        self.assertIn("herdr-worktree --prompt-file <brief file> <branch>", start_line)
        self.assertNotIn("--fork", start_line)
        self.assertIn("lane-brief.md", start_line)
        self.assertNotIn("herdr-worktree --fork", LANE_BRIEF_FILE.read_text())


if __name__ == "__main__":
    unittest.main()
