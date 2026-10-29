import glob
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = pathlib.Path(
    os.environ.get("PLAN_FORMAT_SCRIPT") or REPO_ROOT / "claude" / ".claude" / "scripts" / "lib" / "plan_format.py"
)
sys.path.insert(0, str(SCRIPT.parent))
import plan_format

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
        for body in (
            "N/A.",
            "N/A (docs-only).",
            "- N/A beyond tests; the live check is Phase 8.",
            "N/A — scripts only",
        ):
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
        text = (
            "### Phase 1: x\n\n### Success Criteria\n\n### Automated Verification:\n\n- `make test` passes.\n\n"
            "### Manual Verification:\n\n- [ ] b\n\n### Testing Strategy\n\n### Manual Verification:\n\n- [ ] late\n"
        )
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

    def test_a_tilde_fence_and_an_indented_fence_hide_headings_too(self):
        lines = [
            "## Phase Status",
            "- [ ] Phase 1: A",
            "## Phase 1: A",
            "~~~",
            "## Not a section",
            "~~~",
            "  - step",
            "    ```sh",
            "    # comment",
            "    ```",
            "tail",
            "",
        ]
        plan = plan_format.parse_plan_with_closing_phases(lines)
        self.assertEqual(len(lines), plan["sections"]["1"]["end"])
        self.assertEqual([], plan["failures"])

    def test_phase_status_line_formats_a_real_plan_can_use(self):
        lines = ["## Phase Status", "",
                 "- [ ] Phase 6C2: Deep id (risk: low).",
                 "- [X] Phase 7 — capital X and em dash (risk: high)",
                 "- [ ] Phase 8. Period after number (risk: Low)",
                 "-  [ ]  Phase  9:  Extra spaces (risk: low)",
                 "* [ ] Phase 10 – En dash and star bullet",
                 "- [ ] Phase 11: No risk tag"]
        entries = plan_format.parse_plan_with_closing_phases(lines)["entries"]
        self.assertEqual(["6C2", "7", "8", "9", "10", "11"], [e["number"] for e in entries])
        self.assertEqual(["low", "high", "low", "low", "high", "high"], [e["risk"] for e in entries])
        self.assertEqual([False, True, False, False, False, False], [e["done"] for e in entries])

    def test_logged_phase_id_shapes_parse_look_up_and_mark_done(self):
        ids = ["10.5", "8.6b", "4.6", "7.5", "8.6", "P4", "P9", "1-2", "6A-6D", "P9-slice-1"]
        status_lines = [f"- [ ] Phase {i}: Title {i} (risk: low)" for i in ids]
        sections = [f"## Phase {i}: Title {i}\nbody {i}" for i in ids]
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        plan_path = pathlib.Path(tmp.name) / "ids.md"
        plan_path.write_text("\n".join(["## Phase Status", "", *status_lines, "", *sections, ""]))
        plan_lines = plan_path.read_text().splitlines()
        self.assertEqual(ids, [e["number"] for e in plan_format.parse_plan_with_closing_phases(plan_lines)["entries"]])
        for i in ids:
            self.assertEqual(f"## Phase {i}: Title {i}\nbody {i}", plan_format.phase_text(plan_lines, i))
            plan_format.mark_phase_done(plan_path, i)
        self.assertEqual([True] * len(ids), [e["done"] for e in plan_format.parse_plan_with_closing_phases(
            plan_path.read_text().splitlines())["entries"]])

    def test_parse_plan_fails_a_status_entry_with_no_section_unless_it_is_a_closing_phase(self):
        lines = ["## Phase Status", f"- [ ] Phase {self.ONE}: build", f"- [ ] Phase {self.TWO}: Recap", ""]
        def closing(title):
            return "/branch-recap" if title.startswith("Recap") else None
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
    def gates(self, *status_lines):
        entries, failures = plan_format.phase_status_entries(["## Phase Status", *status_lines], lambda title: None)
        self.assertEqual([], failures)
        return [entry["gate"] for entry in entries]

    def test_a_gate_clause_carries_its_condition_text_and_plain_title_words_are_no_clause(self):
        cases = [
            ("clause carries the condition", ["- [ ] Phase 8: Review family — gate: LED-5 merged"],
             ["LED-5 merged"]),
            ("no clause has no gate", ["- [ ] Phase 8: Review family (risk: low)"], [None]),
            ("risk mark after the clause is not the condition",
             ["- [ ] Phase 8: Family - gate: LED-5 merged (risk: low)"], ["LED-5 merged"]),
            ("clause with no text is still a gate", ["- [ ] Phase 8: Family — gate:"],
             [plan_format.UNSTATED_GATE]),
            ("the word gate without a colon is no clause",
             ["- [ ] Phase 8: Tighten the gate checks", "- [ ] Phase 9: Slicegate: x"], [None, None]),
            ("gate with a colon in plain title text is no clause",
             ["- [ ] Phase 8: Add the review gate: deny drafts", "- [ ] Phase 9: Fix the gate:keeper flow"],
             [None, None]),
            ("dash-joined clause after title text is a clause",
             ["- [ ] Phase 8: Add the review gate - gate: LED-5 merged",
              "- [ ] Phase 9: Fix the flow – gate: LED-6 merged"], ["LED-5 merged", "LED-6 merged"]),
        ]
        for name, status_lines, expected in cases:
            with self.subTest(name):
                self.assertEqual(expected, self.gates(*status_lines))


REAL_MOVED_LINE = ("- [-] Phase 11: Work Mac runs (risk: high) — moved to LED-16 "
                   "(`docs/tickets/LED-16-work-mac-rollout.md`), per agent-ledger-1d 2026-10-20; see Plan Deviations")
REAL_DEVIATION = ("- 2026-10-20: Phase 11 (work Mac runs) moves to a new ticket, LED-16. Ruled by agent-ledger-1d, "
                  "delegated by Brandon 2026-10-20. Brandon's words, 2026-10-20: \"do i NEED to do all this now\"")


class MovedPhaseTest(unittest.TestCase):
    def plan(self, status_line=REAL_MOVED_LINE, deviations=("## Plan Deviations", "", REAL_DEVIATION)):
        lines = ["## Phase Status", "", "- [x] Phase 10: Runs (risk: low)", status_line, "",
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
        self.assertIn("the sign-off for the move in Plan Deviations (who and when), and name Phase 11 and LED-16 in "
                      "the same line.", detail)
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

    def test_an_entry_that_does_not_name_the_phase_and_the_moved_to_key_in_one_line_does_not_record_the_move(self):
        tick_entry = ("- 2026-10-21 (Phase 11): marked done with `tick`, outside the coder, review and verification "
                     "steps of /code.")
        cases = [
            ("a tick entry that names the phase", [tick_entry]),
            ("phase and key on two lines", ["- 2026-10-20: Phase 11 is deferred.",
                                            "- 2026-10-20: the rollout goes to LED-16."]),
            ("a longer key", ["- 2026-10-20: Phase 11 moves to LED-160."]),
            ("another key", ["- 2026-10-20: Phase 11 moves to LED-17."]),
            ("a key with a prefix", ["- 2026-10-20: Phase 11 moves to XLED-16."]),
        ]
        for name, entries in cases:
            with self.subTest(name):
                plan = self.plan(deviations=("## Plan Deviations", "", *entries))
                self.assertEqual(["moved-without-deviation"], self.kinds(plan))
                self.assertIn("LED-16", plan["failures"][0]["detail"])

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
                plan = plan_format.parse_plan([*lines, entry])
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


class BelowCriteriaDeviationTest(unittest.TestCase):
    BLOCK = "PLAN-IMPACT:\n  assumed: a header row\n  found: none - src/a.ts:3\n  changes: drop the skip\n"

    def test_below_criteria_deviations_reads_only_the_entries_the_rule_adopted(self):
        ruling = plan_format.below_criteria_ruling(self.BLOCK + "  acceptance_criteria: none")
        adopted = plan_format.ruling_deviation("2", "Adopt plan change", plan_format.SESSION_RULING_OWNER,
                                               "2026-10-28 10:00", ruling, self.BLOCK)
        user_ruled = plan_format.ruling_deviation("1", "Keep plan as written", "Pat", "2026-10-28 09:00",
                                                  "keep it", self.BLOCK)
        plan_text = "\n".join(["# Plan", "", "## Plan Deviations", "", *user_ruled, "", *adopted, "",
                               "## References", f"  The ruling: {ruling}"])

        summary = "assumed: a header row found: none - src/a.ts:3 changes: drop the skip"
        self.assertEqual(f"{plan_format.BELOW_CRITERIA_RULING} {summary}", ruling)
        self.assertEqual([f"Phase 2: {summary}"], plan_format.below_criteria_deviations(plan_text))
        self.assertEqual([f"Phase 2: {summary}"], plan_format.below_criteria_deviations(plan_text, "2"))
        self.assertEqual([], plan_format.below_criteria_deviations(plan_text, "1"))

    def test_the_summary_drops_bold_marks_before_the_header_word_and_leaves_no_stray_dash(self):
        bold = "**plan_impact**: assumed: a header row —\n  acceptance_criteria: none\n  found: none"
        self.assertEqual("assumed: a header row found: none", plan_format.below_criteria_summary(bold))
        self.assertEqual(f"{plan_format.BELOW_CRITERIA_RULING} assumed: a header row found: none",
                         plan_format.below_criteria_ruling(bold))


class LoudFailureTest(unittest.TestCase):
    def assert_fails_at(self, text, line_number):
        with self.assertRaises(plan_format.PlanFormatError) as caught:
            parse(text)
        self.assertTrue(str(caught.exception).startswith(f"plan.md:{line_number}:"), str(caught.exception))

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


@unittest.skipUnless(toolkit_paths.REAL_PLANS_ENABLED, toolkit_paths.REAL_PLANS_SKIP_REASON)
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
        item_count = 0
        for path in paths:
            with self.subTest(path=path):
                items = plan_format.manual_verification(pathlib.Path(path).read_text(errors="replace"), path)
                item_count += len(items)
                self.assertTrue(all(item["line"] > 0 and item["text"] for item in items))
        print(f"parsed {len(paths)} of {len(paths)} real plan files, {item_count} Manual Verification items",
              file=sys.stderr)

    def test_every_real_phase_status_line_marked_moved_parses_with_its_section_and_deviation_entry(self):
        paths = sorted(glob.glob(str(pathlib.Path.home() / "dev" / "*" / "docs" / "plans" / "*" / "spec.md")))
        if not paths:
            self.skipTest("no real plans on this machine")
        moved_count = 0
        moved_kinds = {"unparsed-line", "section-without-status", "moved-without-target", "moved-without-deviation"}
        for path in paths:
            lines = pathlib.Path(path).read_text(errors="replace").splitlines()
            dash_lines = [line for line in lines if line.startswith("- [-] Phase ")]
            plan = plan_format.parse_plan(lines)
            with self.subTest(path=path):
                self.assertEqual([], [f for f in plan["failures"] if f["kind"] in moved_kinds])
                self.assertEqual(len(dash_lines), sum(1 for entry in plan["entries"] if entry["moved"]))
            moved_count += len(dash_lines)
        print(
            f"parsed {len(paths)} of {len(paths)} real plans, {moved_count} moved Phase Status lines", file=sys.stderr
        )


class RealPlansOptInTest(unittest.TestCase):
    """A broken plan under ~/dev fails the real-plan sweep only when REAL_PLANS=1 asks for it."""

    def setUp(self):
        temp_home = tempfile.TemporaryDirectory()
        self.addCleanup(temp_home.cleanup)
        self.home = pathlib.Path(temp_home.name)

        plan_dir = self.home / "dev" / "some-repo" / "docs" / "plans" / "some-task"
        plan_dir.mkdir(parents=True)
        (plan_dir / "spec.md").write_text("#### Manual Verification:\n\n- [ ] x\n| a | b |\n")

    def run_sweep(self, **environment):
        sweep_env = {key: value for key, value in os.environ.items() if key != "REAL_PLANS"}
        sweep_env.update(HOME=str(self.home), **environment)
        return subprocess.run(
            [sys.executable, "-m", "unittest", "test_plan_format.RealPlansTest"],
            cwd=pathlib.Path(__file__).parent, env=sweep_env, capture_output=True, text=True, check=False,
        )

    def test_the_default_run_skips_a_broken_real_plan(self):
        sweep = self.run_sweep()

        self.assertEqual(0, sweep.returncode, sweep.stderr)
        self.assertIn("skipped", sweep.stderr)

    def test_real_plans_set_to_1_fails_on_a_broken_real_plan(self):
        sweep = self.run_sweep(REAL_PLANS="1")

        self.assertNotEqual(0, sweep.returncode, sweep.stderr)


AUTOMATED_PLAN = """# Plan

## Phase 1: Build it

#### Automated Verification:

- [ ] **Test-verified**: passes - `LEDGER_PY=/x/e.py cargo test --lib`
- [x] **Lint**: clean - `npm run lint`
  indented note
- N/A not an item

#### Manual Verification:

- [ ] open the page

## Phase 2: Ship it

### Automated Verification

- [ ] **Check**: `GATE=1 make check`
"""


class AutomatedVerificationRowsTest(unittest.TestCase):
    def test_rows_are_the_top_level_items_under_the_automated_heading_with_their_indexes(self):
        lines = AUTOMATED_PLAN.splitlines()

        rows = plan_format.automated_verification_rows(lines)

        self.assertEqual([6, 7, 9], [index for index, _ in rows])
        self.assertEqual("- [ ] N/A not an item", rows[2][1])
        self.assertTrue(rows[0][1].startswith("- [ ] **Test-verified**"))

    def test_a_manual_verification_item_and_a_level_three_heading_are_not_rows(self):
        lines = AUTOMATED_PLAN.splitlines()

        rows = [line for _, line in plan_format.automated_verification_rows(lines)]

        self.assertNotIn("- [ ] open the page", rows)
        self.assertNotIn("- [ ] **Check**: `GATE=1 make check`", rows)

    def test_a_heading_of_level_one_to_three_ends_the_list(self):
        for heading in ("# Next", "## Phase 2: Next", "### Notes"):
            with self.subTest(heading=heading):
                lines = ["#### Automated Verification:", "- [ ] a `x`", heading, "- [ ] b `y`"]

                self.assertEqual([(1, "- [ ] a `x`")], plan_format.automated_verification_rows(lines))

    def test_a_misworded_verification_heading_raises_with_its_file_line_and_the_expected_heading(self):
        for heading in ("#### Automated Verfication Steps (verif)", "#### Verification (automated)",
                        "#### automated verification checks"):
            with self.subTest(heading=heading):
                lines = ["text", heading, "- [ ] a `x`"]

                with self.assertRaises(plan_format.PlanFormatError) as raised:
                    plan_format.automated_verification_rows(lines, "plan.md", 10, strict=True)

                self.assertIn("plan.md:11:", str(raised.exception))
                self.assertIn(plan_format.AUTOMATED_HEADING, str(raised.exception))
                self.assertIn("#### Manual Verification:", str(raised.exception))

    def test_a_plain_list_item_under_automated_verification_is_read_as_an_open_box(self):
        for strict in (False, True):
            with self.subTest(strict=strict):
                lines = ["#### Automated Verification:", "- [ ] a `x`", "- `make test`", "* `make lint`", "1. `make b`"]

                rows = plan_format.automated_verification_rows(lines, strict=strict)

                self.assertEqual([(1, "- [ ] a `x`"), (2, "- [ ] `make test`"), (3, "- [ ] `make lint`"),
                                  (4, "- [ ] `make b`")], rows)

    def test_a_plain_n_a_list_item_is_read_as_an_n_a_item(self):
        for item in ("- N/A — docs only", "- N/A: recap only", "- N/A. No gates."):
            with self.subTest(item=item):
                lines = ["#### Automated Verification:", item]

                [(_, line)] = plan_format.automated_verification_rows(lines)

                self.assertTrue(plan_format.NO_AUTOMATED_CHECK.match(line))

    def test_indented_lines_and_items_outside_the_section_are_not_plain_list_items(self):
        lines = ["- `make test`", "#### Automated Verification:", "- [ ] a `x`", "  - Done: ran it", "   1. step",
                 "#### Manual Verification:", "- open the page"]

        self.assertEqual([(2, "- [ ] a `x`")], plan_format.automated_verification_rows(lines, strict=True))
        self.assertEqual([], plan_format.plain_verification_item_warnings(lines))

    def test_a_plain_list_item_warns_with_its_file_line_and_the_checkbox_form(self):
        lines = ["#### Automated Verification:", "- [ ] a `x`", "- `make test`"]

        warnings = plan_format.plain_verification_item_warnings(lines, "plan.md", 10)

        self.assertEqual(1, len(warnings))
        self.assertIn("plan.md:12: warning:", warnings[0])
        self.assertIn("- [ ] <check>", warnings[0])

    def test_a_misworded_heading_reads_as_no_items_unless_strict(self):
        lines = ["#### Verification (automated)", "- [ ] a `x`"]

        self.assertEqual([], plan_format.automated_verification_rows(lines))

    def test_other_level_four_headings_are_not_misworded_verification_headings(self):
        for heading in ("#### Manual Verification:", "#### Manual Verification (cannot be automated):",
                        "#### Success Criteria", "#### Automated tests"):
            with self.subTest(heading=heading):
                lines = [heading, "- [ ] a `x`"]
                self.assertEqual([], plan_format.automated_verification_rows(lines, strict=True))

    def test_a_horizontal_rule_ends_the_list(self):
        lines = ["#### Automated Verification:", "- [ ] a `x`", "---", "- [ ] b `y`"]

        self.assertEqual([(1, "- [ ] a `x`")], plan_format.automated_verification_rows(lines))


class GateEnvTest(unittest.TestCase):
    def test_gate_env_text_names_the_variables_and_says_where_to_put_them(self):
        self.assertEqual("gate-env: A=1 B=2\n(Put these variables before every test, check or build command you run.)",
                         plan_format.gate_env_text(["A=1", "B=2"]))

    def test_gate_env_text_is_empty_when_there_are_no_variables(self):
        self.assertEqual("", plan_format.gate_env_text([]))

    def test_gate_env_is_the_leading_assignments_of_the_automated_commands(self):
        self.assertEqual(["LEDGER_PY=/x/e.py"], plan_format.gate_env(AUTOMATED_PLAN))

    def test_a_plan_with_no_automated_assignment_gives_none(self):
        self.assertEqual([], plan_format.gate_env("#### Automated Verification:\n\n- [ ] a `cargo test`\n"))

    def test_shell_and_prose_spans_of_real_plans_give_no_variables(self):
        spans = ["n=$(ledger count) && test \"$n\" = 3", "S=...; cargo test", "PATH=/x/bin:$PATH cargo test",
                 "T=$(find . -name x) cargo test", "src=index pass=done"]
        plan = "#### Automated Verification:\n\n" + "".join(f"- [ ] **T**: sees `{span}` here\n" for span in spans)

        self.assertEqual([], plan_format.gate_env(plan))

    def test_an_item_the_code_step_never_runs_gives_no_variables(self):
        items = ["- [ ] **CI-verified**: the pipeline runs `FULL_E2E=1 npm test`",
                 "- [ ] Human-only: open the page, then `SHOW_ALL=1 npm start`",
                 "- [ ] N/A - docs only, no `DOCS_ONLY=1 make docs`"]
        for item in items:
            with self.subTest(item=item):
                self.assertEqual([], plan_format.gate_env("#### Automated Verification:\n\n" + item + "\n"))

    def test_an_item_that_is_run_still_gives_its_variables_beside_one_that_is_not(self):
        plan = ("#### Automated Verification:\n\n- [ ] **CI-verified**: runs `FULL_E2E=1 npm test`\n"
                "- [ ] **Unit**: `QUICK=1 npm test`\n")

        self.assertEqual(["QUICK=1"], plan_format.gate_env(plan))

    def test_the_item_tags_are_read_the_same_for_the_gate_env_and_the_run(self):
        self.assertEqual("CI-verified", plan_format.deferred_verification_tag("- [ ] **ci-verified**: the pipeline"))
        self.assertEqual("human-only", plan_format.deferred_verification_tag("- [x] Human-only: a look"))
        self.assertIsNone(plan_format.deferred_verification_tag("- [ ] **Unit**: `npm test`, not CI-verified"))
        self.assertIsNotNone(plan_format.NO_AUTOMATED_CHECK.match("- [ ] **Test-verified**: N/A on the machines."))

    def test_an_item_runs_no_command_when_it_says_n_a_or_is_left_to_ci_or_a_person(self):
        for item in ("- [ ] N/A - docs only", "- [x] none", "- [ ] **Test-verified**: N/A on the machines.",
                     "- [ ] **CI-verified**: the pipeline runs `npm test`", "- [ ] Human-only: look at the page"):
            with self.subTest(item=item):
                self.assertTrue(plan_format.runs_no_command(item))

    def test_an_item_with_a_command_runs_it_even_when_it_mentions_ci_or_n_a_later(self):
        for item in ("- [ ] **Unit**: `npm test`, not CI-verified", "- [ ] **Check**: `make check` (N/A on mac)",
                     "- [ ] `RUN x`"):
            with self.subTest(item=item):
                self.assertFalse(plan_format.runs_no_command(item))

    def test_the_item_text_is_the_line_without_its_box_and_edge_spaces(self):
        self.assertEqual("**Unit**: `npm test`", plan_format.automated_item_text("  - [ ] **Unit**: `npm test`  "))
        self.assertEqual("done", plan_format.automated_item_text("- [x]   done"))
        self.assertEqual("", plan_format.automated_item_text("- [ ]"))


class RepoGateEnvTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = pathlib.Path(directory.name)

    def write_plan(self, folder, command):
        plan_dir = self.root / "docs/plans" / folder
        plan_dir.mkdir(parents=True)
        (plan_dir / "spec.md").write_text(
            f"## Phase 1: X\n\n#### Automated Verification:\n\n- [ ] **T**: `{command}`\n"
        )
        return f"docs/plans/{folder}/spec.md"

    def test_a_repo_with_no_plans_has_no_gate_env(self):
        self.assertEqual([], plan_format.repo_gate_env(self.root))

    def test_plans_that_agree_on_a_value_give_it(self):
        self.write_plan("one", "A=1 cargo test")
        self.write_plan("two", "A=1 B=2 cargo test")

        self.assertEqual(["A=1", "B=2"], sorted(plan_format.repo_gate_env(self.root)))

    def test_plans_that_disagree_on_a_value_leave_the_name_out(self):
        self.write_plan("one", "A=1 cargo test")
        self.write_plan("two", "A=2 cargo test")
        self.write_plan("three", "B=3 cargo test")

        self.assertEqual(["B=3"], plan_format.repo_gate_env(self.root))

    def test_the_plan_of_the_run_decides_its_own_value_over_the_others(self):
        self.write_plan("one", "A=1 cargo test")
        own_plan = self.write_plan("two", "A=2 cargo test")
        self.write_plan("three", "A=3 cargo test")

        self.assertEqual(["A=2"], plan_format.repo_gate_env(self.root, own_plan))

    def test_the_plan_of_the_run_takes_no_name_that_only_other_plans_set(self):
        self.write_plan("one", "B=9 cargo test")
        own_plan = self.write_plan("two", "A=2 cargo test")

        self.assertEqual(["A=2"], plan_format.repo_gate_env(self.root, own_plan))

    def test_a_plan_with_no_names_gives_none_even_when_other_plans_agree(self):
        self.write_plan("one", "B=9 cargo test")
        own_plan = self.write_plan("two", "cargo test")

        self.assertEqual([], plan_format.repo_gate_env(self.root, own_plan))

    def test_shell_junk_in_other_plans_adds_no_names_and_literal_settings_stay(self):
        self.write_plan("one", "n=$(ledger count) && test 1 = 1")
        self.write_plan("two", "PATH=/x/bin:$PATH cargo test")
        self.write_plan("three", "T=$(find . -name x) cargo test")
        self.write_plan("four", "src=index pass=done")
        self.write_plan("five", "S=...; cargo test")
        self.write_plan("six", "CARGO_BUILD_JOBS=4 cargo test")

        self.assertEqual(["CARGO_BUILD_JOBS=4"], plan_format.repo_gate_env(self.root))

    def test_an_old_plan_with_a_misworded_verification_heading_does_not_stop_the_read(self):
        old_dir = self.root / "docs/plans/old"
        old_dir.mkdir(parents=True)
        old_plan = "## Phase 1: X\n\n#### Verification (automated):\n\n- [ ] `A=1 cargo test`\n"
        (old_dir / "spec.md").write_text(old_plan)
        self.write_plan("current", "B=2 cargo test")

        self.assertEqual(["B=2"], plan_format.repo_gate_env(self.root))

    def test_a_plan_path_that_does_not_exist_is_read_as_a_plan_with_no_names(self):
        self.write_plan("one", "B=9 cargo test")

        self.assertEqual(["B=9"], plan_format.repo_gate_env(self.root, "docs/plans/gone/spec.md"))


CLOSING_PLAN = """## Phase Status

- [ ] Phase 1: Build
- [ ] Phase 2: Gated work — gate: LED-5 merged
- [x] Phase 3: Refactor pass
- [ ] Phase 4: Verify pass
- [ ] Phase 5: Later work

## Phase 1: Build

build text

## Phase 2: Gated work

gated text

## Phase 5: Later work

later text

## References
"""


class ClosingPhaseHelpersTest(unittest.TestCase):
    def entries(self, text=CLOSING_PLAN):
        plan = plan_format.parse_plan_with_closing_phases(text.split("\n"))
        self.assertEqual([], plan["failures"])
        return plan["entries"]

    def test_a_closing_title_names_its_skill_and_any_other_title_names_none(self):
        self.assertEqual("/refactor +deep", plan_format.closing_skill("Refactor pass"))
        self.assertEqual("/test-audit", plan_format.closing_skill("test audit"))
        self.assertEqual("/verify-branch", plan_format.closing_skill("Verify pass"))
        self.assertEqual("/branch-recap", plan_format.closing_skill("Recap"))
        self.assertIsNone(plan_format.closing_skill("Verify pass for the orders API"))
        self.assertIsNone(plan_format.closing_skill("Build it"))

    def test_the_closing_phases_are_recognised_and_need_no_section(self):
        closing = [(entry["number"], entry["closing"]) for entry in self.entries()]
        self.assertEqual([("1", None), ("2", None), ("3", "/refactor +deep"), ("4", "/verify-branch"), ("5", None)],
                         closing)

    def test_phase_text_is_the_section_or_none(self):
        lines = CLOSING_PLAN.split("\n")
        self.assertEqual("## Phase 1: Build\n\nbuild text\n", plan_format.phase_text(lines, "1"))
        self.assertIsNone(plan_format.phase_text(lines, "4"))

    def test_phase_wording_ignores_checked_boxes_and_done_evidence_but_not_new_words(self):
        written = "## Phase 1: Build\n- [ ] builds\n"
        ticked = "## Phase 1: Build\n- [x] builds\n  - Done: ran it\n"
        changed = "## Phase 1: Build\n- [ ] builds twice\n"
        self.assertEqual(plan_format.phase_wording(written), plan_format.phase_wording(ticked))
        self.assertNotEqual(plan_format.phase_wording(written), plan_format.phase_wording(changed))

    def test_open_phases_come_in_plan_order_with_the_closing_phases_last(self):
        text = CLOSING_PLAN.replace("- [x] Phase 3", "- [ ] Phase 3")
        pending = plan_format.ordered_pending(self.entries(text))
        self.assertEqual(["1", "2", "5", "3", "4"], [entry["number"] for entry in pending])

    def test_gate_blockers_are_the_gated_phases_ahead_of_the_first_phase_without_a_gate(self):
        pending = plan_format.ordered_pending(self.entries())
        gated_ahead, next_ungated = plan_format.gate_blockers(pending)
        self.assertEqual([], gated_ahead)
        self.assertEqual("1", next_ungated["number"])

        gated_ahead, next_ungated = plan_format.gate_blockers(pending[1:])
        self.assertEqual(["2"], [entry["number"] for entry in gated_ahead])
        self.assertEqual("5", next_ungated["number"])

        gated_ahead, next_ungated = plan_format.gate_blockers(pending[1:2])
        self.assertEqual(["2"], [entry["number"] for entry in gated_ahead])
        self.assertIsNone(next_ungated)

    def test_the_gate_block_text_names_each_gate_and_the_next_phase_without_one(self):
        pending = plan_format.ordered_pending(self.entries())[1:]
        gated_ahead, next_ungated = plan_format.gate_blockers(pending)
        text = plan_format.gate_block_text(gated_ahead, next_ungated)
        self.assertIn("Phase 2 (gate: LED-5 merged)", text)
        self.assertIn("The next open phase without a gate is Phase 5.", text)
        self.assertTrue(text.endswith("`start --phase <id>` runs one anyway."))
        self.assertNotIn("without a gate", plan_format.gate_block_text(gated_ahead, None))

    def test_the_moved_phase_text_and_stop_name_the_target_ticket(self):
        entry = {"number": "11", "moved": True, "movedTo": "LED-16"}
        other = {"number": "12", "moved": False, "movedTo": None}
        self.assertEqual("Phase 11 to LED-16", plan_format.moved_phase_text([entry, other]))
        before_coder = plan_format.moved_phase_stop(entry, "spec.md")
        self.assertIn("Phase 11 is moved to LED-16 in spec.md", before_coder)
        self.assertIn("No coder was dispatched.", before_coder)
        after_coder = plan_format.moved_phase_stop(entry, "spec.md", coder_ran=True)
        self.assertIn("The coder ran, and its work is not marked done or committed.", after_coder)

    def test_the_failure_rows_name_the_plan_line_kind_and_detail(self):
        plan = {"failures": [{"line": 4, "kind": "duplicate-id", "detail": "Phase 1 twice"}]}
        self.assertEqual(["spec.md:4: duplicate-id: Phase 1 twice"], plan_format.plan_failure_rows(plan, "spec.md"))
        message = plan_format.plan_failure_message(plan, "spec.md")
        self.assertTrue(message.startswith("The plan's Phase Status does not parse."))
        self.assertTrue(message.endswith("spec.md:4: duplicate-id: Phase 1 twice"))


class PlanFileEditTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.plan_path = pathlib.Path(folder.name) / "spec.md"
        self.plan_path.write_text(CLOSING_PLAN)

    def test_marking_a_phase_done_checks_only_its_open_status_line(self):
        plan_format.mark_phase_done(self.plan_path, "1")
        text = self.plan_path.read_text()
        self.assertIn("- [x] Phase 1: Build", text)
        self.assertIn("- [ ] Phase 2: Gated work", text)
        self.assertEqual(CLOSING_PLAN.replace("- [ ] Phase 1", "- [x] Phase 1"), text)

    def test_marking_a_done_or_unknown_phase_changes_nothing(self):
        plan_format.mark_phase_done(self.plan_path, "3")
        plan_format.mark_phase_done(self.plan_path, "99")
        self.assertEqual(CLOSING_PLAN, self.plan_path.read_text())

    def test_reopening_unchecks_the_done_closing_phases_and_names_them(self):
        reopened = plan_format.reopen_closing_phases(self.plan_path)
        self.assertEqual(["3"], reopened)
        self.assertIn("- [ ] Phase 3: Refactor pass", self.plan_path.read_text())
        self.assertEqual([], plan_format.reopen_closing_phases(self.plan_path))

    def test_a_deviation_makes_its_section_before_the_references(self):
        plan_format.append_deviation(self.plan_path, ["- 2026-10-24: Phase 2 waits."])
        lines = self.plan_path.read_text().split("\n")
        self.assertEqual(["## Plan Deviations", "", "- 2026-10-24: Phase 2 waits.", "", "## References"],
                         lines[lines.index("## Plan Deviations"):lines.index("## References") + 1])

    def test_a_deviation_joins_the_end_of_the_section_the_plan_has(self):
        self.plan_path.write_text("## Plan Deviations\n\n- first\n\n## References\n")
        plan_format.append_deviation(self.plan_path, ["- second"])
        self.assertEqual("## Plan Deviations\n\n- first\n\n- second\n\n## References\n", self.plan_path.read_text())

    def test_a_section_heading_inside_a_code_fence_does_not_end_the_deviations_section(self):
        self.plan_path.write_text("## Plan Deviations\n\n- first\n\n```\n## sample\n```\n\n## References\n")
        plan_format.append_deviation(self.plan_path, ["- second"])
        self.assertEqual("## Plan Deviations\n\n- first\n\n```\n## sample\n```\n\n- second\n\n## References\n",
                         self.plan_path.read_text())

    def test_a_deviation_goes_to_the_end_when_the_plan_has_no_references(self):
        self.plan_path.write_text("## Phase 1: a\n\ntext\n")
        plan_format.append_deviation(self.plan_path, ["- note"])
        self.assertEqual("## Phase 1: a\n\ntext\n\n## Plan Deviations\n\n- note\n", self.plan_path.read_text())

    def test_a_ruling_entry_names_the_phase_decision_owner_ruling_and_disagreement(self):
        entry = plan_format.ruling_deviation("2", "Adopt plan change", "Pat Signer", "2026-10-25 09:30",
                                             "use the  new\ntable", "assumed: one table\nfound: two")
        self.assertEqual(["- 2026-10-25 (Phase 2): Adopt plan change. Ruled by Pat Signer at 2026-10-25 09:30.", "",
                          "  The ruling: use the new table", "", "  The disagreement:", "  assumed: one table",
                          "  found: two"], entry)

    def test_a_ruling_entry_with_no_phase_leaves_the_phase_out(self):
        entry = plan_format.ruling_deviation(None, "Keep plan as written", "the session, not the user",
                                             "2026-10-25 09:30", "keep it", "found: two")
        self.assertEqual("- 2026-10-25: Keep plan as written. Ruled by the session, not the user at 2026-10-25 09:30.",
                         entry[0])


class ManualFormatHelpersTest(unittest.TestCase):
    GOOD = ("## Phase 1: a\n\n#### Manual Verification:\n\n- [ ] open it\n\n## Phase 2: b\n\n"
            "#### Manual Verification:\n\n- [ ] read it\n")
    BAD = "## Phase 1: a\n\n#### Manual Verification:\n\n- [ ] open it\n| a | b |\n"

    def test_the_items_of_one_phase_or_all_phases(self):
        lines = self.GOOD.split("\n")
        self.assertEqual(["open it"], [i["text"] for i in plan_format.phase_manual_items(lines, 1, "spec.md")])
        self.assertEqual(["open it", "read it"],
                         [i["text"] for i in plan_format.phase_manual_items(lines, None, "spec.md")])

    def test_a_section_that_parses_has_no_failure_message(self):
        self.assertIsNone(plan_format.manual_format_failure(self.GOOD.split("\n"), "spec.md"))

    def test_a_section_that_does_not_parse_gives_the_stop_message_and_the_resume_line(self):
        message = plan_format.manual_format_failure(self.BAD.split("\n"), "spec.md", "Then run resume.")
        self.assertTrue(message.startswith("The plan's Manual Verification section does not parse."))
        self.assertIn("spec.md", message)
        self.assertTrue(message.endswith("\nThen run resume."))
        self.assertFalse(plan_format.manual_format_message("boom").endswith("\n"))


if __name__ == "__main__":
    unittest.main()
