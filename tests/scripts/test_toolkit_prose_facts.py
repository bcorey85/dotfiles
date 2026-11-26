"""Facts the corrected skill and agent prompts state: each line names one action and none contradicts another."""
import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from toolkit_paths import CLAUDE_DIR, LIB_DIR, OPENCODE_AGENTS_DIR

sys.path.insert(0, str(LIB_DIR))
import script_utils

ARCHITECTS = ("backend-architect", "frontend-architect")
CALIBRATION_FILE = CLAUDE_DIR / "skills" / "_shared" / "reviewer-calibration.md"
GATE_SENTENCE = "That justification line is the gate."


def skill_text(name):
    return (CLAUDE_DIR / "skills" / name / "SKILL.md").read_text()


def description_of(agent_file):
    value = script_utils.frontmatter_value(agent_file.read_text(), "description")
    assert value, f"no description in {agent_file}"
    return value.strip().strip('"')


def markdown_files(*folders):
    return sorted(file for folder in folders for file in folder.rglob("*.md"))


def consumers_line(shared_file):
    for line in shared_file.read_text().splitlines():
        if line.startswith("Consumers:"):
            return line
    raise AssertionError(f"no Consumers: line in {shared_file}")


def consumer_token(relative_path):
    """How a consumers line names the file at `relative_path` (relative to the claude dir)."""
    parts = relative_path.split("/")
    if parts[0] == "agents":
        return parts[1].removesuffix(".md")
    if parts[0] == "skills" and "scripts" not in parts:
        return f"/{parts[1]}"
    return relative_path


def citing_tokens(cited_name, own_file):
    """The consumer token of every toolkit file under the claude dir, and every opencode agent port,
    that names `cited_name`."""
    tokens = set()
    for folder in ("agents", "skills", "scripts"):
        for file in sorted((CLAUDE_DIR / folder).rglob("*")):
            if not file.is_file() or file == own_file or "__pycache__" in file.parts:
                continue
            if cited_name not in file.read_text(errors="ignore"):
                continue
            tokens.add(consumer_token(file.relative_to(CLAUDE_DIR).as_posix()))
    for port in sorted(OPENCODE_AGENTS_DIR.glob("*.md")):
        if cited_name in port.read_text(errors="ignore"):
            tokens.add(port.stem)
    return tokens


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
        expected_names = {
            "plan-verifier": ("/verify-branch", "/close-branch"),
            "test-intent-reviewer": ("/test-audit", "/close-branch", "scope: bug-pinning"),
        }
        for agent, names in expected_names.items():
            description = description_of(CLAUDE_DIR / "agents" / f"{agent}.md")
            for name in names:
                self.assertIn(name, description, agent)

    def test_opencode_test_intent_reviewer_names_test_audit_only(self):
        description = description_of(OPENCODE_AGENTS_DIR / "test-intent-reviewer.md")
        self.assertIn("/test-audit", description)
        self.assertNotIn("close-branch", description)

    def test_architect_descriptions_are_two_sentences_naming_eng_spec_phase_4(self):
        agent_dirs = (CLAUDE_DIR / "agents", OPENCODE_AGENTS_DIR)
        for agent_dir in agent_dirs:
            for agent in ARCHITECTS:
                description = description_of(agent_dir / f"{agent}.md")
                label = f"{agent_dir}/{agent}"
                kind = agent.removesuffix("-architect")
                self.assertEqual(description.count(". "), 1, label)
                self.assertTrue(description.startswith(f"Designs {kind} features"), label)
                self.assertTrue(description.endswith("Dispatched by /eng-spec phase 4."), label)

    def test_architect_core_owns_reuse_map_rules_and_brief_and_agents_do_not_repeat(self):
        core = skill_text("architect-core")
        self.assertIn("## Reuse Map", core)
        self.assertIn("Reuse Inventory", core)
        self.assertIn("exploration brief", core)
        self.assertIn("Invariant survey", core)
        self.assertIn(GATE_SENTENCE, core)
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
        calibration = CALIBRATION_FILE.read_text()
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
        self.assertRegex(coder_core, r"Otherwise:\n\n- Run the typecheck")

    def test_goal_blind_researcher_and_opencode_port_both_list_the_repair_loop_branches(self):
        claude_text = (CLAUDE_DIR / "agents" / "goal-blind-researcher.md").read_text()
        port_text = (OPENCODE_AGENTS_DIR / "goal-blind-researcher.md").read_text()
        for text in (claude_text, port_text):
            self.assertIn("**Repair loop, bounded at two cycles.**\n", text)
            self.assertIn("   - A flag with no rewrite", text)
            self.assertNotIn("Then go to step 4. A flag with no", text)

    def test_no_architect_agent_or_eng_spec_file_carries_the_reuse_map_gate_or_seed_sentence(self):
        folders = (CLAUDE_DIR / "agents", CLAUDE_DIR / "skills" / "eng-spec", OPENCODE_AGENTS_DIR)
        for file in markdown_files(*folders):
            text = file.read_text()
            self.assertNotIn(GATE_SENTENCE, text, str(file))
            self.assertNotIn("Seed it from", text, str(file))

    def test_every_claude_skill_and_agent_pointer_names_a_file_that_exists(self):
        pointer = re.compile(r"~/\.claude/((?:skills|agents)/[A-Za-z0-9_./-]+\.md)")
        all_files = markdown_files(CLAUDE_DIR, OPENCODE_AGENTS_DIR)
        # Installed plugins live under plugins/ and carry their own docs, which point at their own agents.
        plugin_dir = CLAUDE_DIR / "plugins"
        files = [file for file in all_files if not file.is_relative_to(plugin_dir)]
        self.assertTrue(files)
        for file in files:
            for target in pointer.findall(file.read_text()):
                self.assertTrue((CLAUDE_DIR / target).is_file(), f"{file} points at missing {target}")
        for deleted in ("design-decision-format.md", "finding-log.md", "skimmable-writing.md"):
            self.assertEqual(list(CLAUDE_DIR.rglob(deleted)), [], deleted)

    def test_every_bare_shared_pointer_in_a_script_names_a_file_that_exists(self):
        pointer = re.compile(r"_shared/[A-Za-z0-9_-]+\.md")
        skills_dir = CLAUDE_DIR / "skills"
        script_folders = [CLAUDE_DIR / "scripts", *sorted(skills_dir.glob("*/scripts"))]
        script_files = sorted(
            file for folder in script_folders for file in folder.rglob("*") if file.is_file() and not file.is_symlink()
        )
        self.assertTrue(script_files)
        for file in script_files:
            try:
                text = file.read_text()
            except UnicodeDecodeError:
                continue
            for target in pointer.findall(text):
                self.assertTrue((skills_dir / target).is_file(), f"{file} points at missing {target}")

    def test_the_decisions_phase_keeps_alternatives_rejected_and_the_emoji_heading_line(self):
        decisions = (CLAUDE_DIR / "skills" / "eng-spec" / "phases" / "5-decisions.md").read_text()
        self.assertIn("Alternatives rejected", decisions)
        self.assertIn("Start each block's heading with an emoji for its kind", decisions)

    def test_the_spec_template_and_plan_format_keep_their_evidence_and_criterion_test_rules(self):
        template = (CLAUDE_DIR / "skills" / "eng-spec" / "templates" / "spec-template.md").read_text()
        self.assertIn("may NOT rest on declared-only", template)
        plan_format = (CLAUDE_DIR / "skills" / "_shared" / "plan-format.md").read_text()
        self.assertIn("No mocks inside such a test.", plan_format)

    def test_list_names_the_file_with_the_full_text_and_pull_ticket_states_the_three_statuses(self):
        self.assertIn("Name the file that holds the full text (report, diff) once", skill_text("list"))
        pull_ticket = skill_text("pull-ticket")
        self.assertIn("'In Review' or 'Done': warn", pull_ticket)

    def test_test_intent_reviewer_scopes_the_cull_to_test_audit_and_close_branch(self):
        text = (CLAUDE_DIR / "agents" / "test-intent-reviewer.md").read_text()
        self.assertIn("- **`scope: cull`** (from `/test-audit` and `/close-branch`, the assembled branch diff)", text)

    def test_explore_phase_carries_no_invariant_survey(self):
        phase = (CLAUDE_DIR / "skills" / "eng-spec" / "phases" / "4-explore.md").read_text()
        self.assertNotIn("invariant", phase.lower())

    def test_no_skill_points_at_the_escape_ratchet_with_a_weak_per_or_from_pointer(self):
        weak_pointer = re.compile(r"(per|from) .~/\.claude/skills/_shared/escape-ratchet\.md.")
        for file in markdown_files(CLAUDE_DIR / "skills"):
            self.assertIsNone(weak_pointer.search(file.read_text()), str(file))

    def test_the_shared_consumer_lists_name_the_files_that_cite_them(self):
        shared = CLAUDE_DIR / "skills" / "_shared"
        for name in ("escape-ratchet", "code-vocabulary"):
            shared_file = shared / f"{name}.md"
            listed = set(re.findall(r"`([^`]+)`", consumers_line(shared_file)))
            self.assertEqual(listed, citing_tokens(name, shared_file), name)

    def test_6b_review_has_no_weak_rung_pointer_and_step_19b_is_a_bullet_list(self):
        review = (CLAUDE_DIR / "skills" / "eng-spec" / "phases" / "6b-review.md").read_text()
        self.assertNotIn("is the rung from", review)
        step = review.split("19b. **Shard above 400 lines.**", 1)[1].split("\n20. ", 1)[0]
        lines = [line for line in step.splitlines() if line.strip()]
        self.assertGreaterEqual(len(lines), 5)
        first_unindented = [line for line in lines if not line.startswith("    ")]
        self.assertEqual(first_unindented, [])
        self.assertTrue(lines[0].startswith("    - "), lines[0])

    def test_the_opencode_test_reviewer_port_points_at_the_ports_cull_step(self):
        reviewer = (OPENCODE_AGENTS_DIR / "test-reviewer.md").read_text()
        self.assertIn("Step 4 \N{EM DASH} Cull check", reviewer)
        intent_reviewer = (OPENCODE_AGENTS_DIR / "test-intent-reviewer.md").read_text()
        self.assertIn("## Step 4 \N{EM DASH} Cull check (added tests only)", intent_reviewer)

    def test_review_fork_run_has_its_six_sections_and_calibration_drops_the_silent_failure_line(self):
        fork_run = (CLAUDE_DIR / "skills" / "_shared" / "review-fork-run.md").read_text()
        headings = re.findall(r"^## (.+)$", fork_run, re.MULTILINE)
        self.assertEqual(headings, ["The run folder", "Launch", "Reviewers", "The packet's ACTION lines",
                                    "Ending the run hands back", "Resume"])
        self.assertNotIn("Getting this wrong is silent", CALIBRATION_FILE.read_text())

    def test_review_fork_run_reads_an_existing_review_stop_before_it_writes_it(self):
        fork_run = (CLAUDE_DIR / "skills" / "_shared" / "review-fork-run.md").read_text()
        ending = fork_run.split("## Ending the run hands back", 1)[1].split("\n## ", 1)[0]
        self.assertIn("When that file already exists, Read it first.", ending)


if __name__ == "__main__":
    unittest.main()
