"""Facts the corrected skill and agent prompts state: each line names one action and none contradicts another."""
import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from toolkit_paths import CLAUDE_DIR, REPO_ROOT

OPENCODE_AGENTS_DIR = REPO_ROOT / "opencode" / ".config" / "opencode" / "agents"


def skill_text(name):
    return (CLAUDE_DIR / "skills" / name / "SKILL.md").read_text()


def description_of(agent_file):
    text = agent_file.read_text()
    match = re.search(r'^description:\s*"(.*)"\s*$', text, re.MULTILINE)
    assert match, f"no description in {agent_file}"
    return match.group(1)


def section_of(text, heading):
    parts = re.split(r"^## ", text, flags=re.MULTILINE)
    for part in parts:
        if part.startswith(heading):
            return part
    raise AssertionError(f"no section {heading}")


class ToolkitProseFactsTest(unittest.TestCase):
    def test_verify_branch_does_not_call_itself_the_only_run_site(self):
        self.assertNotIn("only run site", skill_text("verify-branch"))

    def test_orient_boundaries_state_its_only_writes(self):
        boundaries = section_of(skill_text("orient"), "Boundaries")
        self.assertNotIn("Read-only", boundaries)
        self.assertIn("vault note", boundaries)
        self.assertIn("`note`", boundaries)

    def test_todos_allows_only_the_two_git_commands(self):
        text = skill_text("todos")
        self.assertNotIn("Do NOT go looking", text)
        self.assertIn("two git commands", text)

    def test_plan_verifier_and_test_intent_reviewer_name_close_branch(self):
        for agent in ("plan-verifier", "test-intent-reviewer"):
            description = description_of(CLAUDE_DIR / "agents" / f"{agent}.md")
            self.assertIn("/close-branch", description, agent)

    def test_opencode_test_intent_reviewer_names_test_audit_only(self):
        description = description_of(OPENCODE_AGENTS_DIR / "test-intent-reviewer.md")
        self.assertIn("/test-audit", description)
        self.assertNotIn("close-branch", description)


if __name__ == "__main__":
    unittest.main()
