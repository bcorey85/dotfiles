import glob
import os
import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = pathlib.Path(os.environ.get("PLAN_FORMAT_SCRIPT") or REPO_ROOT / "claude" / ".claude" / "scripts" / "plan_format.py")
sys.path.insert(0, str(SCRIPT.parent))
import plan_format  # noqa: E402

TEMPLATE = """# Plan

## Phase 1: Build it

#### Manual Verification:

- [ ] open the page
- [x] ticked item

## Phase 2: Ship it

#### Manual Verification (human-only, Brandon):

- [ ] read the contract
"""


def parse(text):
    return plan_format.manual_verification(text, "plan.md")


class SectionShapeTest(unittest.TestCase):
    def test_template_items_carry_phase_text_checked_state_and_line(self):
        items = parse(TEMPLATE)
        self.assertEqual([(i["phase"], i["text"], i["checked"], i["line"]) for i in items],
                         [("1", "open the page", False, 7), ("1", "ticked item", True, 8),
                          ("2", "read the contract", False, 14)])

    def test_heading_qualifier_is_returned_with_each_item(self):
        items = parse(TEMPLATE)
        self.assertEqual(items[0]["heading"], ":")
        self.assertIn("human-only", items[2]["heading"])

    def test_an_unmarked_item_is_run_by_an_agent_and_agent_verified_marks_in_any_case_do_not_make_it_human_only(self):
        text = ("## Queue\n\n#### Manual Verification (agent-driven):\n\n- [ ] look at it\n"
                "- [x] ran the suite (agent-verified: exit 0)\n- [ ] wrapped\n  agent-verified on the second line\n"
                "- [ ] Agent-Verified in other case\n- [ ] **Agent-verified**: ran it\n- [ ] Agent-verified. Ran it.\n")
        self.assertEqual([i["humanOnly"] for i in parse(text)], [False, False, False, False, False, False])

    def test_an_item_is_verified_when_checked_or_when_an_agent_item_is_marked_agent_verified(self):
        text = ("## Queue\n\n#### Manual Verification:\n\n- [ ] not run\n- [x] ticked\n- [ ] Agent-Verified: ran it\n"
                "- [ ] wrapped\n  agent-verified on the second line\n- [x] human-only but ticked\n")
        self.assertEqual([i["verified"] for i in parse(text)], [False, True, True, True, True])

    def test_human_only_in_the_heading_or_the_item_text_in_any_case_makes_the_item_human_only(self):
        text = ("## Queue\n\n#### Manual Verification (human-only, Brandon):\n\n- [ ] read it\n"
                "- [ ] **Agent-verified**: but heading says otherwise\n\n"
                "## Sort\n\n#### Manual Verification:\n\n- [ ] run it\n- [ ] Human-Only: judge the layout\n"
                "- [ ] wrapped\n  (human-only) on the second line\n")
        self.assertEqual([i["humanOnly"] for i in parse(text)], [True, True, False, True, True])

    def test_plain_bullets_numbered_steps_and_indented_lines_fold_into_items(self):
        text = ("## Phase 3: x\n\n#### Manual Verification (agent-driven on each machine):\n\n"
                "In a temp root:\n\n"
                "1. Pipe a row.\n2. Run `ledger load`.\n"
                "- These two numbers are equal:\n  - `ledger yield`\n  - `ledger query`\n"
                "- [ ] wrapped\n  second line\n\nExpected: one row.\n")
        items = parse(text)
        self.assertEqual([i["text"] for i in items],
                         ["Pipe a row.", "Run `ledger load`.",
                          "These two numbers are equal: - `ledger yield` - `ledger query`", "wrapped second line"])
        self.assertTrue(all(not i["checked"] for i in items))

    def test_not_applicable_lines_are_accepted_and_yield_no_item(self):
        for body in ("N/A.", "N/A (docs-only).", "- N/A beyond tests; the live check is Phase 8.", "N/A — scripts only"):
            with self.subTest(body=body):
                self.assertEqual(parse(f"## Phase 1: x\n\n#### Manual Verification:\n\n{body}\n\n## Phase 2: y\n"), [])

    def test_a_bare_manual_verification_line_outside_a_heading_is_not_a_section(self):
        self.assertEqual(parse("## Phase 1: x\n\nManual Verification: N/A (docs-only).\n- not an item\n"), [])

    def test_section_ends_at_the_next_heading_or_a_rule(self):
        text = "#### Manual Verification:\n\n- [ ] one\n\n---\n\n- [ ] after the rule\n"
        self.assertEqual([i["text"] for i in parse(text)], ["one"])
        text = "#### Manual Verification:\n\n- [ ] one\n\n#### Automated Verification:\n\n- `make test` passes.\n"
        self.assertEqual([i["text"] for i in parse(text)], ["one"])

    def test_a_level_3_section_parses_with_its_phase(self):
        text = "## Phase 1: x\n\n### Manual Verification (human-only):\n\n- [ ] look at it\n- [x] done one\n"
        items = parse(text)
        self.assertEqual([(i["phase"], i["text"], i["checked"], i["humanOnly"]) for i in items],
                         [("1", "look at it", False, True), ("1", "done one", True, True)])

    def test_a_level_3_section_under_a_level_3_phase_heading_keeps_the_phase(self):
        self.assertEqual(["2"], [i["phase"] for i in parse("### Phase 2: x\n\n### Manual Verification\n\n- [ ] a\n")])

    def test_a_level_3_section_ends_at_the_next_level_2_or_3_heading_and_leaves_later_sections_apart(self):
        for stopper in ("## Next", "### Next"):
            with self.subTest(stopper=stopper):
                text = f"### Manual Verification:\n\n- [ ] one\n\n{stopper}\n\n- [ ] not an item\n"
                self.assertEqual(["one"], [i["text"] for i in parse(text)])
        text = ("### Manual Verification:\n\n- [ ] one\n\n#### Notes\n\nplain prose\n\n"
                "## Phase 2: y\n\n#### Manual Verification:\n\n- [ ] two\n")
        self.assertEqual([("one", None), ("two", "2")], [(i["text"], i["phase"]) for i in parse(text)])

    def test_a_list_item_under_a_deeper_sub_heading_inside_a_section_fails_with_its_line(self):
        text = "### Manual Verification:\n\n- [ ] one\n\n#### Automated Verification:\n\n- `make test` passes.\n"
        with self.assertRaises(plan_format.PlanFormatError) as caught:
            parse(text)
        self.assertTrue(str(caught.exception).startswith("plan.md:7:"), str(caught.exception))
        self.assertIn("Automated Verification", str(caught.exception))

    def test_a_nested_manual_section_does_not_deepen_the_open_section_so_a_later_sub_heading_item_fails(self):
        text = ("### Manual Verification\n\n- [ ] a\n\n#### Manual Verification (human-only)\n\n- [ ] b\n\n"
                "#### Notes\n\n- [ ] c\n")
        with self.assertRaises(plan_format.PlanFormatError) as caught:
            parse(text)
        self.assertTrue(str(caught.exception).startswith("plan.md:11:"), str(caught.exception))
        self.assertIn("move the item above it", str(caught.exception))

    def test_a_phase_stays_open_across_a_level_3_success_criteria_group(self):
        text = ("### Phase 1: x\n\n### Success Criteria\n\n### Automated Verification:\n\n- `make test` passes.\n\n"
                "### Manual Verification:\n\n- [ ] b\n\n### Testing Strategy\n\n### Manual Verification:\n\n- [ ] late\n")
        self.assertEqual([("b", "1"), ("late", None)], [(i["text"], i["phase"]) for i in parse(text)])

    def test_phase_resets_at_a_non_phase_heading_of_the_same_level(self):
        text = "## Phase 1: x\n\n## Testing Strategy\n\n#### Manual Verification:\n\n- [ ] late\n"
        self.assertIsNone(parse(text)[0]["phase"])

    def test_heading_inside_a_fenced_block_is_not_a_section(self):
        text = "## Phase 1: x\n\n```markdown\n#### Manual Verification:\n\n- [ ] quoted template\n```\n"
        self.assertEqual(parse(text), [])

    def test_task_dir_flat_plan_without_phases_gives_phase_none(self):
        items = parse("# Plan\n\n## Queue\n\n#### Manual Verification:\n\n- [ ] human-only: look at it\n")
        self.assertIsNone(items[0]["phase"])


class LoudFailureTest(unittest.TestCase):
    def assert_fails_at(self, text, lineNumber):
        with self.assertRaises(plan_format.PlanFormatError) as caught:
            parse(text)
        self.assertTrue(str(caught.exception).startswith(f"plan.md:{lineNumber}:"), str(caught.exception))

    def test_a_heading_level_other_than_3_or_4_fails_instead_of_dropping_the_items(self):
        for marks in ("##", "#####"):
            with self.subTest(marks=marks):
                self.assert_fails_at(f"# P\n\n{marks} Manual Verification:\n\n- [ ] x\n", 3)
        with self.assertRaises(plan_format.PlanFormatError) as caught:
            parse("## Manual Verification:\n\n- [ ] x\n")
        self.assertIn("level 3 or level 4", str(caught.exception))

    def test_fenced_block_inside_the_section_fails(self):
        self.assert_fails_at("#### Manual Verification:\n\n- [ ] x\n\n```bash\nmake\n```\n", 5)

    def test_table_quote_and_html_lines_fail(self):
        for line in ("| a | b |", "> quoted", "<!-- note -->"):
            with self.subTest(line=line):
                self.assert_fails_at(f"#### Manual Verification:\n\n- [ ] x\n{line}\n", 4)

    def test_indented_line_with_no_item_above_it_fails(self):
        self.assert_fails_at("#### Manual Verification:\n\nIntro:\n  stray indented\n", 4)
        self.assert_fails_at("#### Manual Verification:\n\n- N/A beyond tests\n  detail\n", 4)


class RealPlansTest(unittest.TestCase):
    """Every real plan under ~/dev/*/docs/{plans,eng-specs}/ parses, and every section yields phase-tagged items."""

    def plan_paths(self):
        found = set()
        for root in ("plans", "eng-specs"):
            found.update(glob.glob(str(pathlib.Path.home() / "dev" / "*" / "docs" / root / "**" / "*.md"),
                                   recursive=True))
        return sorted(found)

    def test_every_real_plan_parses(self):
        paths = self.plan_paths()
        if not paths:
            self.skipTest("no real plans on this machine")
        itemCount = 0
        for path in paths:
            with self.subTest(path=path):
                items = plan_format.manual_verification(pathlib.Path(path).read_text(errors="replace"), path)
                itemCount += len(items)
                self.assertTrue(all(item["line"] > 0 and item["text"] for item in items))
        print(f"parsed {len(paths)} of {len(paths)} real plan files, {itemCount} Manual Verification items",
              file=sys.stderr)


if __name__ == "__main__":
    unittest.main()
