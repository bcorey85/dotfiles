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

    def test_general_purpose_body_is_four_lines_and_keeps_the_report_rule(self):
        claude_text = (CLAUDE_DIR / "agents" / "general-purpose.md").read_text()
        frontmatter_end = claude_text.index("---", 3) + 3
        body_lines = [line for line in claude_text[frontmatter_end:].splitlines() if line.strip()]
        self.assertEqual(len(body_lines), 4)
        port_text = (OPENCODE_AGENTS_DIR / "general-purpose.md").read_text()
        kept_rule_fragments = (
            "editing an existing file",
            "README files",
            "always absolute, never relative",
            "Never state an unverified claim as fact.",
        )
        for fragment in kept_rule_fragments:
            self.assertIn(fragment, claude_text)
            self.assertIn(fragment, port_text)
        for removed in ("Your strengths", "Guidelines:", "Be thorough"):
            self.assertNotIn(removed, claude_text)
            self.assertNotIn(removed, port_text)


    def test_blocker_reproduction_sentence_is_gone_from_review_fork_run_and_calibration_self_check(self):
        calibration = (CLAUDE_DIR / "skills" / "_shared" / "reviewer-calibration.md").read_text()
        self_check = calibration.split("run the calibration question one more time", 1)[1]
        self.assertNotIn("names its reproduction", self_check)
        fork_run = (CLAUDE_DIR / "skills" / "_shared" / "review-fork-run.md").read_text()
        self.assertNotIn("names its reproduction", fork_run)

    def test_spec_research_search_rules_are_bullets_and_edit_rule_is_a_paragraph(self):
        text = (CLAUDE_DIR / "agents" / "spec-research.md").read_text()
        bullets = [line for line in text.splitlines() if line.startswith("- ")]
        self.assertIn("- Search file contents only with `rg` in Bash.", bullets)
        self.assertIn("- Never search file contents with `grep -r`, `find -exec` or `git grep`.", bullets)
        edit_lines = [line for line in text.splitlines() if line.startswith("Change a file only with Edit or Write")]
        self.assertEqual(len(edit_lines), 1)
        self.assertNotIn("skips the Write and Edit hooks", text)

    def test_decisions_step_14_has_no_nested_bold_paragraphs_and_coder_core_verify_tail_is_cut(self):
        decisions = (CLAUDE_DIR / "skills" / "eng-spec" / "phases" / "5-decisions.md").read_text()
        self.assertIn("    - **Before the list:**", decisions)
        self.assertNotIn("\n    **Before the list:**", decisions)
        coder_core = skill_text("coder-core")
        self.assertNotIn("leaves the run going with no output", coder_core)
        self.assertNotIn("so output you cut off is lost", coder_core)

    def test_goal_blind_researcher_and_opencode_port_both_list_the_repair_loop_branches(self):
        claude_text = (CLAUDE_DIR / "agents" / "goal-blind-researcher.md").read_text()
        port_text = (OPENCODE_AGENTS_DIR / "goal-blind-researcher.md").read_text()
        for text in (claude_text, port_text):
            self.assertIn("**Repair loop, bounded at two cycles.**\n", text)
            self.assertIn("   - A flag with no rewrite", text)
            self.assertNotIn("Then go to step 4. A flag with no", text)


if __name__ == "__main__":
    unittest.main()
