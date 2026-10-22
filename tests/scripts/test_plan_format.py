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


class PhaseSectionsTest(unittest.TestCase):
    ONE = "6"
    DOTTED = "6.1"
    TWO = "7"

    def spans(self, *lines):
        return plan_format.phase_spans(list(lines))

    def test_a_phase_is_found_by_its_exact_id_when_a_dotted_id_with_the_same_prefix_comes_first(self):
        lines = [f"## Phase {self.DOTTED}: dotted", "a", f"## Phase {self.ONE}: whole", "b"]
        section = plan_format.phase_section(lines, self.ONE)
        self.assertEqual((2, 4), (section["start"], section["end"]))
        self.assertIsNone(plan_format.phase_section(lines[:2], self.ONE))

    def test_a_second_section_of_one_id_is_a_failure_and_still_gets_its_span(self):
        spans, failures = self.spans(f"## Phase {self.ONE}: a", "x", f"## Phase {self.ONE}: again", "y")
        self.assertEqual([(self.ONE, 0, 2), (self.ONE, 2, 4)], [(i, s["start"], s["end"]) for i, s in spans])
        self.assertEqual([("duplicate-id", 3)], [(f["kind"], f["line"]) for f in failures])

    def test_a_deeper_heading_of_an_id_that_has_a_section_is_a_note_inside_it(self):
        spans, failures = self.spans(f"## Phase {self.ONE}: a", f"#### Phase {self.ONE} record", "x", "## Other")
        self.assertEqual([(self.ONE, 0, 3)], [(i, s["start"], s["end"]) for i, s in spans])
        self.assertEqual([], failures)

    def test_a_deeper_heading_of_a_new_id_ends_the_section_it_sits_in(self):
        spans, _ = self.spans(f"## Phase {self.ONE}: a", f"### Phase {self.TWO}: b", "x")
        self.assertEqual([(self.ONE, 0, 1), (self.TWO, 1, 3)], [(i, s["start"], s["end"]) for i, s in spans])

    def test_a_section_stays_open_across_its_own_level_success_groups_and_ends_at_the_next_other_heading(self):
        spans, _ = self.spans(f"### Phase {self.ONE}: a", "### Automated Verification", "x", "### Manual Verification",
                              "y", "### Notes", "z")
        self.assertEqual([(self.ONE, 0, 5)], [(i, s["start"], s["end"]) for i, s in spans])

    def test_a_heading_inside_a_fenced_block_starts_no_section(self):
        spans, _ = self.spans(f"## Phase {self.ONE}: a", "```", f"## Phase {self.TWO}: fake", "```", "x")
        self.assertEqual([(self.ONE, 0, 5)], [(i, s["start"], s["end"]) for i, s in spans])

    def test_parse_plan_fails_a_status_entry_with_no_section_unless_it_is_a_closing_phase(self):
        lines = ["## Phase Status", f"- [ ] Phase {self.ONE}: build", f"- [ ] Phase {self.TWO}: Recap", ""]
        closing = lambda title: "/branch-recap" if title.startswith("Recap") else None
        plan = plan_format.parse_plan(lines, closing)
        self.assertEqual([(1, "missing-section")], [(f["line"] - 1, f["kind"]) for f in plan["failures"]])
        self.assertEqual([None, "/branch-recap"], [e["closing"] for e in plan["entries"]])

    def test_parse_plan_fails_a_section_the_status_list_does_not_name(self):
        lines = ["## Phase Status", f"- [ ] Phase {self.ONE}: build", f"## Phase {self.ONE}: build",
                 f"## Phase {self.TWO}: extra"]
        plan = plan_format.parse_plan(lines)
        self.assertEqual(["section-without-status"], [f["kind"] for f in plan["failures"]])
        self.assertEqual(4, plan["failures"][0]["line"])


class PhaseGateClauseTest(unittest.TestCase):
    def gates(self, *statusLines):
        entries, failures = plan_format.phase_status_entries(["## Phase Status", *statusLines], lambda title: None)
        self.assertEqual([], failures)
        return [entry["gate"] for entry in entries]

    def test_a_status_title_with_a_gate_clause_carries_the_condition_text(self):
        self.assertEqual(["LED-5 merged"], self.gates("- [ ] Phase 8: Review family — gate: LED-5 merged"))

    def test_a_status_title_with_no_gate_clause_has_no_gate(self):
        self.assertEqual([None], self.gates("- [ ] Phase 8: Review family (risk: low)"))

    def test_the_risk_mark_after_a_gate_clause_is_not_part_of_the_condition(self):
        self.assertEqual(["LED-5 merged"], self.gates("- [ ] Phase 8: Family - gate: LED-5 merged (risk: low)"))

    def test_a_gate_clause_with_no_text_is_still_a_gate(self):
        self.assertEqual([plan_format.UNSTATED_GATE], self.gates("- [ ] Phase 8: Family — gate:"))

    def test_the_word_gate_inside_a_title_without_a_colon_is_not_a_clause(self):
        self.assertEqual([None, None], self.gates("- [ ] Phase 8: Tighten the gate checks",
                                                  "- [ ] Phase 9: Slicegate: x"))

    def test_gate_with_a_colon_in_plain_title_text_is_not_a_clause(self):
        self.assertEqual([None, None], self.gates("- [ ] Phase 8: Add the review gate: deny drafts",
                                                  "- [ ] Phase 9: Fix the gate:keeper flow"))

    def test_a_dash_joined_gate_clause_after_title_text_is_a_clause(self):
        self.assertEqual(["LED-5 merged", "LED-6 merged"],
                         self.gates("- [ ] Phase 8: Add the review gate - gate: LED-5 merged",
                                    "- [ ] Phase 9: Fix the flow – gate: LED-6 merged"))


REAL_MOVED_LINE = ("- [-] Phase 11: Work Mac runs (risk: high) — moved to LED-16 "
                   "(`docs/tickets/LED-16-work-mac-rollout.md`), per agent-ledger-1d 2026-10-20; see Plan Deviations")
REAL_DEVIATION = ("- 2026-10-20: Phase 11 (work Mac runs) moves to a new ticket, LED-16. Ruled by agent-ledger-1d, "
                  "delegated by Brandon 2026-10-20. Brandon's words, 2026-10-20: \"do i NEED to do all this now\"")


class MovedPhaseTest(unittest.TestCase):
    def plan(self, statusLine=REAL_MOVED_LINE, deviations=("## Plan Deviations", "", REAL_DEVIATION)):
        lines = ["## Phase Status", "", "- [x] Phase 10: Runs (risk: low)", statusLine, "",
                 "## Phase 10: Runs", "text", "", "## Phase 11: Work Mac runs — moved to LED-16", "handed off", ""]
        return plan_format.parse_plan(lines + list(deviations))

    def kinds(self, plan):
        return [failure["kind"] for failure in plan["failures"]]

    def test_the_real_moved_line_with_its_deviation_entry_parses_and_is_neither_done_nor_open(self):
        plan = self.plan()
        entry = next(entry for entry in plan["entries"] if entry["number"] == "11")
        self.assertEqual([], plan["failures"])
        self.assertEqual((True, False, "LED-16"), (entry["moved"], entry["done"], entry["movedTo"]))
        self.assertEqual((False, True), (plan["entries"][0]["moved"], plan["entries"][0]["done"]))

    def test_a_moved_line_without_a_target_ticket_fails_and_says_to_add_it(self):
        plan = self.plan("- [-] Phase 11: Work Mac runs (risk: high) — deferred, see Plan Deviations")
        self.assertEqual(["moved-without-target"], self.kinds(plan))
        self.assertEqual(4, plan["failures"][0]["line"])
        self.assertIn("moved to <KEY>", plan["failures"][0]["detail"])
        self.assertNotIn("- [ ] Phase", plan["failures"][0]["detail"])

    def test_a_target_must_be_a_ticket_key(self):
        for title in ("moved to later", "moved to LED16", "moved to led-16 maybe"):
            with self.subTest(title=title):
                plan = self.plan(f"- [-] Phase 11: Work Mac runs (risk: high) — {title}")
                self.assertEqual(["moved-without-target"], self.kinds(plan))

    def test_a_moved_phase_with_no_deviation_entry_naming_it_fails_and_says_to_record_the_sign_off(self):
        plan = self.plan(deviations=())
        self.assertEqual(["moved-without-deviation"], self.kinds(plan))
        self.assertEqual(4, plan["failures"][0]["line"])
        detail = plan["failures"][0]["detail"]
        self.assertIn("the sign-off for the move in Plan Deviations (who, when, their words)", detail)
        self.assertNotIn("user's", detail)

    def test_a_moved_phase_may_have_no_section_of_its_own(self):
        lines = ["## Phase Status", "", "- [x] Phase 10: Runs (risk: low)", REAL_MOVED_LINE, "",
                 "## Phase 10: Runs", "text", "", "## Plan Deviations", "", REAL_DEVIATION]
        plan = plan_format.parse_plan(lines)
        self.assertNotIn("11", plan["sections"])
        self.assertEqual([], plan["failures"])

    def test_an_open_phase_with_no_section_still_fails(self):
        lines = ["## Phase Status", "", "- [ ] Phase 10: Runs (risk: low)", "- [ ] Phase 11: Mac runs", "",
                 "## Phase 10: Runs", "text"]
        plan = plan_format.parse_plan(lines)
        self.assertEqual(["missing-section"], self.kinds(plan))

    def test_a_tick_entry_that_names_the_phase_does_not_record_the_move(self):
        tickEntry = ("- 2026-10-21 (Phase 11): marked done with `tick`, outside the coder, review and verification "
                     "steps of /code.")
        plan = self.plan(deviations=("## Plan Deviations", "", tickEntry))
        self.assertEqual(["moved-without-deviation"], self.kinds(plan))
        self.assertIn("LED-16", plan["failures"][0]["detail"])

    def test_the_phase_and_the_ticket_key_must_be_named_in_one_line(self):
        plan = self.plan(deviations=("## Plan Deviations", "", "- 2026-10-20: Phase 11 is deferred.",
                                     "- 2026-10-20: the rollout goes to LED-16."))
        self.assertEqual(["moved-without-deviation"], self.kinds(plan))

    def test_the_key_in_the_entry_must_stand_alone_and_be_the_key_the_line_moves_to(self):
        for entry in ("- 2026-10-20: Phase 11 moves to LED-160.", "- 2026-10-20: Phase 11 moves to LED-17.",
                      "- 2026-10-20: Phase 11 moves to XLED-16."):
            with self.subTest(entry=entry):
                plan = self.plan(deviations=("## Plan Deviations", "", entry))
                self.assertEqual(["moved-without-deviation"], self.kinds(plan))

    def test_a_phase_id_that_starts_with_p_is_named_by_the_id_or_by_phase_and_the_id(self):
        lines = ["## Phase Status", "", "- [x] Phase P3: Runs", "- [-] Phase P4: Mac runs — moved to LED-16", "",
                 "## Phase P3: Runs", "text", "", "## Plan Deviations", ""]
        for entry, expected in (("- 2026-10-20: P4 moves to LED-16.", []),
                                ("- 2026-10-20: Phase P4 moves to LED-16.", []),
                                ("- 2026-10-20: Phase 4 moves to LED-16.", ["moved-without-deviation"]),
                                ("- 2026-10-20: PP4 moves to LED-16.", ["moved-without-deviation"]),
                                ("- 2026-10-20: P40 moves to LED-16.", ["moved-without-deviation"]),
                                ("- 2026-10-20: P3 moves to LED-16.", ["moved-without-deviation"])):
            with self.subTest(entry=entry):
                plan = plan_format.parse_plan(lines + [entry])
                self.assertEqual(expected, self.kinds(plan))

    def test_an_entry_that_names_another_phase_does_not_count(self):
        for entry in ("- 2026-10-20: Phase 1 moves to LED-16.", "- 2026-10-20: Phase 110 moves to LED-16.",
                      "- 2026-10-20: Phase 11.2 moves to LED-16.", "- 2026-10-20: TOP11 moves to LED-16."):
            with self.subTest(entry=entry):
                plan = self.plan(deviations=("## Plan Deviations", "", entry))
                self.assertEqual(["moved-without-deviation"], self.kinds(plan))

    def test_an_entry_names_the_phase_as_phase_or_p_in_a_bullet_or_a_numbered_item(self):
        for entry in ("1. **Phase 11 moved to LED-16** (2026-10-20).", "- P11 moved to LED-16.",
                      "- **2026-10-20, Phase 11 (work Mac runs).** Moved to LED-16.",
                      "- 2026-10-20: moved Phase 11 to LED-16.", "- P11, moved to LED-16."):
            with self.subTest(entry=entry):
                plan = self.plan(deviations=("## Plan Deviations", "", entry))
                self.assertEqual([], plan["failures"])

    def test_the_check_does_not_judge_who_signed_the_entry(self):
        plan = self.plan(deviations=("## Plan Deviations", "", "- Phase 11 moves to LED-16."))
        self.assertEqual([], plan["failures"])

    def test_a_mention_outside_the_plan_deviations_section_does_not_count(self):
        before = ("## Notes", "Phase 11 moves to LED-16.", "", "## Plan Deviations", "", "- Phase 9 changed.")
        after = ("## Plan Deviations", "", "- Phase 9 changed.", "", "## Later notes", "Phase 11 moves to LED-16.")
        for deviations in (before, after):
            with self.subTest(deviations=deviations):
                self.assertEqual(["moved-without-deviation"], self.kinds(self.plan(deviations=deviations)))

    def test_moved_phases_lists_only_the_dash_marked_entries_of_a_plan_text(self):
        text = "\n".join(["## Phase Status", "- [ ] Phase 1: a", REAL_MOVED_LINE, "- [x] Phase 2: b", "",
                          "## Plan Deviations", REAL_DEVIATION])
        self.assertEqual([("11", "LED-16")], [(e["number"], e["movedTo"]) for e in plan_format.moved_phases(text)])
        self.assertEqual([], plan_format.moved_phases("no phase status here"))

    def test_moved_phases_raises_with_the_name_and_line_for_a_moved_line_with_no_key(self):
        text = "\n".join(["## Phase Status", "- [ ] Phase 1: a", "- [-] Phase 2: b — deferred", "",
                          "## Plan Deviations", "- Phase 2 deferred."])
        with self.assertRaises(plan_format.PlanFormatError) as caught:
            plan_format.moved_phases(text, "spec.md")
        self.assertTrue(str(caught.exception).startswith("spec.md:3:"), str(caught.exception))
        self.assertIn("moved to <KEY>", str(caught.exception))

    def test_moved_phases_raises_with_the_name_and_line_for_a_moved_line_no_deviation_records(self):
        text = "\n".join(["## Phase Status", "- [ ] Phase 1: a", "- [-] Phase 2: b — moved to LED-16", "",
                          "## Plan Deviations", "- 2026-10-21 (Phase 2): marked done with `tick`."])
        with self.assertRaises(plan_format.PlanFormatError) as caught:
            plan_format.moved_phases(text, "spec.md")
        self.assertTrue(str(caught.exception).startswith("spec.md:3:"), str(caught.exception))
        self.assertIn("Plan Deviations", str(caught.exception))

    def test_open_and_done_lines_are_unmoved(self):
        entries, failures = plan_format.phase_status_entries(
            ["## Phase Status", "- [ ] Phase 1: a", "- [x] Phase 2: b", "- [X] Phase 3: c",
             "- [-] Phase 4: d — moved to LED-16"], lambda title: None)
        self.assertEqual([], failures)
        self.assertEqual([(False, False), (False, True), (False, True), (True, False)],
                         [(e["moved"], e["done"]) for e in entries[:4]])
        self.assertEqual([True, False, False, False], [e["open"] for e in entries])


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

    def test_every_real_phase_status_line_marked_moved_parses_with_its_section_and_deviation_entry(self):
        paths = sorted(glob.glob(str(pathlib.Path.home() / "dev" / "*" / "docs" / "plans" / "*" / "spec.md")))
        if not paths:
            self.skipTest("no real plans on this machine")
        movedCount = 0
        movedKinds = {"unparsed-line", "section-without-status", "moved-without-target", "moved-without-deviation"}
        for path in paths:
            lines = pathlib.Path(path).read_text(errors="replace").splitlines()
            dashLines = [line for line in lines if line.startswith("- [-] Phase ")]
            plan = plan_format.parse_plan(lines)
            with self.subTest(path=path):
                self.assertEqual([], [f for f in plan["failures"] if f["kind"] in movedKinds])
                self.assertEqual(len(dashLines), sum(1 for entry in plan["entries"] if entry["moved"]))
            movedCount += len(dashLines)
        print(f"parsed {len(paths)} of {len(paths)} real plans, {movedCount} moved Phase Status lines", file=sys.stderr)


if __name__ == "__main__":
    unittest.main()
