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


ARCHITECTS = ("backend-architect", "frontend-architect")


def plain_description_of(agent_file):
    text = agent_file.read_text()
    match = re.search(r"^description:\s*(.+?)\s*$", text, re.MULTILINE)
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

    def test_architect_descriptions_are_one_sentence_naming_eng_spec_phase_4(self):
        agent_dirs = (CLAUDE_DIR / "agents", OPENCODE_AGENTS_DIR)
        for agent_dir in agent_dirs:
            for agent in ARCHITECTS:
                description = plain_description_of(agent_dir / f"{agent}.md")
                label = f"{agent_dir}/{agent}"
                self.assertEqual(description.count(". "), 1, label)
                self.assertTrue(description.endswith("."), label)
                self.assertIn("/eng-spec phase 4", description, label)

    def test_architect_core_owns_reuse_map_rules_and_brief_and_agents_do_not_repeat(self):
        core = skill_text("architect-core")
        self.assertIn("## Reuse Map", core)
        self.assertIn("Reuse Inventory", core)
        self.assertIn("exploration brief", core)
        self.assertIn("Invariant survey", core)
        for agent in ARCHITECTS:
            body = (CLAUDE_DIR / "agents" / f"{agent}.md").read_text()
            self.assertNotIn("Reuse Inventory", body, agent)
            self.assertNotIn("justification line", body, agent)
            self.assertNotIn("Invariant survey", body, agent)
            self.assertNotIn("Counter-priming", body, agent)

    def test_eng_spec_explore_phase_points_at_architect_core(self):
        phase = (CLAUDE_DIR / "skills" / "eng-spec" / "phases" / "4-explore.md").read_text()
        self.assertIn("architect-core", phase)

    def test_opencode_architect_ports_load_architect_core_first(self):
        for agent in ARCHITECTS:
            body = (OPENCODE_AGENTS_DIR / f"{agent}.md").read_text()
            first_action = re.search(r"^\*\*First action\*\*.*$", body, re.MULTILINE)
            self.assertIsNotNone(first_action, agent)
            self.assertIn("architect-core/SKILL.md", first_action.group(0), agent)


if __name__ == "__main__":
    unittest.main()
