import glob
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = pathlib.Path(
    os.environ.get("PLAN_FORMAT_SCRIPT") or REPO_ROOT / "claude" / ".claude" / "scripts" / "lib" / "plan_format.py"
)
sys.path.insert(0, str(SCRIPT.parent))
import plan_format
import script_utils
import signoff_lines
import standing_rulings

sys.path.insert(0, str(toolkit_paths.CODE_DIR))
import coder_report

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


class PlanFormatPathCharsTest(unittest.TestCase):
    def test_plan_regexes_read_dollar_and_plus_paths(self):
        found = plan_format.PATH_IN_BACKTICKS.findall("edit `src/routes/$id.tsx:12` and `src/routes/+page.svelte:3`")
        self.assertEqual(found, ["src/routes/$id.tsx", "src/routes/+page.svelte"])
        for line in ("src/routes/$id.ts:12 [bug] PLAN-IMPACT: x", "`src/routes/+page.svelte:3` PLAN-IMPACT: x"):
            with self.subTest(line=line):
                mark = plan_format.PLAN_CHANGE_MARK.match(line)
                self.assertIsNotNone(mark)
                self.assertTrue(line[:mark.end()].upper().endswith("PLAN-IMPACT"))

    def test_a_file_entry_on_a_dollar_path_names_that_path(self):
        plan_lines = ["- **File**: `src/routes/$id.tsx`", "- **Files**: `src/routes/+page.svelte:3`"]
        section = {"start": 0, "end": len(plan_lines)}
        paths = plan_format.file_entry_paths(plan_lines, section)
        self.assertEqual(paths, {"src/routes/$id.tsx", "src/routes/+page.svelte"})


class PlanChangeMarkTest(unittest.TestCase):
    def test_a_plan_impact_ask_is_marked_whatever_form_its_line_number_takes(self):
        ask = "plan impact: needs a column"
        lines = {
            "a line": f"`app.py:13` {ask}",
            "a bare line": f"app.py:13 {ask}",
            "a range": f"`app.py:13-14` {ask}",
            "an en dash range": f"`app.py:13\N{EN DASH}14` {ask}",
            "a list of ranges": f"`backend/src/schema.ts:58-101,139-147` {ask}",
            "a list of lines": f"`app.py:3,9` {ask}",
            "a tag after a range": f"`app.py:3-5` [plan-drift] \N{EM DASH} {ask}",
            "a tag before a range": f"[plan-drift] `app.py:3-5` {ask}",
            "a wrapped prefix in backticks": "`PLAN-IMPACT:` app.py:3 \N{EM DASH} x",
            "a wrapped prefix in bold": "**PLAN-IMPACT:** app.py:3 \N{EM DASH} x",
            "a wrapped prefix after a class tag": "[docs] `PLAN-IMPACT:` app.py:3 \N{EM DASH} x",
        }
        for name, line in lines.items():
            with self.subTest(name):
                self.assertIsNotNone(plan_format.PLAN_CHANGE_MARK.match(line))

    def test_text_that_only_mentions_a_plan_impact_later_is_not_marked(self):
        texts = ("`app.py:13-14` the limit is wrong; see the plan impact", "the plan holds", "app.py:13-x plan impact")
        for text in texts:
            with self.subTest(text):
                self.assertIsNone(plan_format.PLAN_CHANGE_MARK.match(text))

    def test_an_ask_tagged_plan_impact_none_is_not_marked(self):
        texts = ("PLAN-IMPACT: none. The limit check belongs in the helper.", "plan_impact: none",
                 "**PLAN-IMPACT:** none.", "`app.py:13` [bug] PLAN-IMPACT: none of substance; move the guard",
                 "PLAN-IMPACT: no", "PLAN-IMPACT: no. Rename the flag.", "`PLAN-IMPACT:` none",
                 "**PLAN-IMPACT: none**")
        for text in texts:
            with self.subTest(text):
                self.assertIsNone(plan_format.PLAN_CHANGE_MARK.match(text))

    def test_an_ask_whose_plan_impact_opens_with_the_word_no_is_still_marked(self):
        self.assertIsNotNone(plan_format.PLAN_CHANGE_MARK.match("PLAN-IMPACT: no index on orders exists; the plan "
                                                                "assumed one. acceptance_criteria: none"))


class ReportBlockTest(unittest.TestCase):
    def test_a_plan_impact_block_is_found_in_each_shape_a_report_writes_it(self):
        block = ("assumed: the table has a key\nfound: it has none\nchanges: add a migration\n"
                 "acceptance_criteria: none")
        shapes = {
            "indented": "BEHAVIOR: none\nPLAN-IMPACT:\n  " + block.replace("\n", "\n  ") + "\nPLAN-IMPACT: yes",
            "keys at column 0": "BEHAVIOR: none\nPLAN-IMPACT:\n" + block + "\ncause: toolkit\nPLAN-IMPACT: yes",
            "bold header and a blank line": "PLAN-IMPACT:**\n\n  " + block.replace("\n", "\n  "),
            "bold keys": ("**PLAN-IMPACT:**\n- **assumed:** a\n- **found:** b\n- **changes:** c\n"
                          "- **acceptance_criteria:** none\n- **cause:** toolkit"),
        }
        causes = {"keys at column 0": "toolkit", "bold keys": "toolkit"}
        for name, report in shapes.items():
            with self.subTest(name):
                found = coder_report.plan_impact_block(report)
                self.assertIsNotNone(found)
                self.assertEqual(causes.get(name, "plan"), plan_format.plan_impact_cause(found))
                self.assertNotIn("block not found", found)
                self.assertIn("assumed", found)
                self.assertIn("changes", found)
                self.assertIn("acceptance_criteria", found)
                self.assertFalse(plan_format.changes_acceptance_criteria(found))

    def test_a_trailing_kind_clause_does_not_make_an_answer_of_none_a_criteria_change(self):
        lines = (
            "`PLAN-IMPACT:` app.py:3 — the cap differs — `acceptance_criteria: none` — `kind: reword`",
            "PLAN-IMPACT: app.py:3 — the cap differs — acceptance_criteria: none — kind: reword",
            "PLAN-IMPACT: app.py:3 — the cap differs — acceptance_criteria: none\nkind: reword",
            "PLAN-IMPACT: app.py:3 — x — acceptance_criteria: none kind: reword",
            "PLAN-IMPACT: app.py:3 — x — `acceptance_criteria: none` `kind: reword`",
            "PLAN-IMPACT: app.py:3 — x — acceptance_criteria: none (ruled in Phase 0)",
            "PLAN-IMPACT: app.py:3 — x — acceptance_criteria: none (AC3 holds either way)",
            "PLAN-IMPACT: app.py:3 — x — acceptance_criteria: none. Delegated.",
        )
        for line in lines:
            with self.subTest(line=line):
                self.assertFalse(plan_format.changes_acceptance_criteria(line))
        self.assertTrue(plan_format.changes_acceptance_criteria(
            "PLAN-IMPACT: app.py:3 — the cap differs — acceptance_criteria: AC2 — kind: reword"))
        self.assertTrue(plan_format.changes_acceptance_criteria(
            "PLAN-IMPACT: app.py:3 — x — acceptance_criteria: none beyond AC1"))
        self.assertEqual(plan_format.criteria_ids(
            "PLAN-IMPACT: x — acceptance_criteria: none (AC3 holds either way)", answers_only=True), frozenset())
        self.assertEqual(plan_format.criteria_ids("acceptance_criteria: `AC2`, `AC3`"), frozenset({"AC2", "AC3"}))

    def test_an_answer_of_none_followed_by_except_but_or_beyond_is_a_criteria_change(self):
        answers = (
            "none, but AC2 wording changes",
            "none — except AC2 narrows",
            "none beyond AC2",
        )
        wrapped = (
            "`PLAN-IMPACT:` a.py:3 — x — `acceptance_criteria: none` but AC2 narrows",
            "PLAN-IMPACT: a.py:3 — x — **acceptance_criteria:** **none** except AC2",
            "PLAN-IMPACT: a.py:3 — x — acceptance_criteria: none; but AC2 wording changes",
        )
        for line in wrapped:
            with self.subTest(line=line):
                self.assertTrue(plan_format.changes_acceptance_criteria(line))
                self.assertEqual(plan_format.criteria_ids(line, answers_only=True), frozenset({"AC2"}))
        for answer in answers:
            with self.subTest(answer=answer):
                line = f"PLAN-IMPACT: app.py:3 — x — acceptance_criteria: {answer}"
                self.assertTrue(plan_format.changes_acceptance_criteria(line))
                self.assertEqual(plan_format.criteria_ids(line, answers_only=True), frozenset({"AC2"}))

    def test_an_answer_of_none_with_a_parenthetical_naming_a_criterion_stays_none(self):
        line = "PLAN-IMPACT: app.py:3 — x — acceptance_criteria: none (AC2 holds either way)"

        self.assertFalse(plan_format.changes_acceptance_criteria(line))
        self.assertEqual(plan_format.criteria_ids(line, answers_only=True), frozenset())

    def test_below_criteria_summary_drops_the_answer_and_its_kind_clause(self):
        shapes = (
            "`PLAN-IMPACT:` a.py:3 — x `acceptance_criteria: none`\n`kind: reword`",
            "PLAN-IMPACT: a.py:3 — x acceptance_criteria: none **kind:** reword",
            "PLAN-IMPACT: a.py:3 — x acceptance_criteria: none (ruled in Phase 0)",
            "PLAN-IMPACT: a.py:3 — x acceptance_criteria: none.",
            "PLAN-IMPACT: a.py:3 — x — acceptance_criteria: none; kind: reword",
            "PLAN-IMPACT: a.py:3 — x — acceptance_criteria: none, kind: reword",
        )
        for shape in shapes:
            with self.subTest(shape=shape):
                summary = plan_format.below_criteria_summary(shape)
                self.assertNotIn("kind", summary)
                self.assertTrue(summary.endswith("— x"), summary)


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

    def test_test_strategy_section_takes_a_level_3_test_strategy_heading_and_its_sub_heading(self):
        lines = ["## Phase 1: x", "", "### Test Strategy", "", "Cover it.", "#### Sub", "more", "### Next", "out"]
        section = plan_format.test_strategy_section(lines)
        self.assertEqual("### Test Strategy\n\nCover it.\n#### Sub\nmore", section)

    def test_test_strategy_range_skips_a_heading_in_a_fence_and_is_none_without_one(self):
        fenced = ["## Phase 1: x", "```", "### Test Strategy", "```", "text"]
        real = ["## Phase 1: x", "```", "### Test Strategy", "```", "## Test Strategy", "rules", "---", "out"]

        self.assertIsNone(plan_format.test_strategy_range(fenced))
        self.assertEqual((4, 6), plan_format.test_strategy_range(real))

    def test_test_strategy_range_ignores_a_heading_in_a_shared_section_before_the_first_phase(self):
        lines = ["## Shared", "### Test Strategy", "early", "## Phase 1: x", "body", "## Test Strategy", "late"]

        self.assertEqual((5, 7), plan_format.test_strategy_range(lines))
        self.assertEqual("## Test Strategy\nlate", plan_format.test_strategy_section(lines))

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

    def test_logged_phase_id_shapes_parse_and_look_up(self):
        ids = ["10.5", "8.6b", "4.6", "7.5", "8.6", "P4", "P9", "1-2", "6A-6D", "P9-slice-1"]
        status_lines = [f"- [ ] Phase {i}: Title {i} (risk: low)" for i in ids]
        sections = [f"## Phase {i}: Title {i}\nbody {i}" for i in ids]
        plan_lines = "\n".join(["## Phase Status", "", *status_lines, "", *sections, ""]).splitlines()
        self.assertEqual(ids, [e["number"] for e in plan_format.parse_plan_with_closing_phases(plan_lines)["entries"]])
        for i in ids:
            self.assertEqual(f"## Phase {i}: Title {i}\nbody {i}", plan_format.phase_text(plan_lines, i))

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
    def test_the_summary_drops_bold_marks_before_the_header_word_and_leaves_no_stray_dash(self):
        bold = "**plan_impact**: assumed: a header row —\n  acceptance_criteria: none\n  found: none"
        self.assertEqual("assumed: a header row found: none", plan_format.below_criteria_summary(bold))
        self.assertEqual(f"{plan_format.BELOW_CRITERIA_RULING} assumed: a header row found: none",
                         plan_format.below_criteria_ruling(bold))


CRITERION_TEXT = "The cache reuses the stored value"
CRITERIA_WITH_TICKET_NOT_CARRIED = "# Acceptance Criteria\n\n- **AC1** — The cache may reuse a stored value\n"
SPEC_WITH_RULING = (f'# Plan\n\n## Plan Deviations\n\n- 2026-11-10: Ticket #1 "{CRITERION_TEXT}" reworded. '
                    "The session ruled it.\n")


class CriteriaOwnerTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = pathlib.Path(folder.name)
        self.queue_dir = self.folder / "home" / "agent-evals" / "queue"
        self.queue_dir.mkdir(parents=True)
        home_patch = mock.patch.dict(os.environ, {"HOME": str(self.folder / "home")})
        home_patch.start()
        self.addCleanup(home_patch.stop)

    def queue_item(self, frontmatter_body, slug="item"):
        (self.queue_dir / f"{slug}.md").write_text(f"---\ntype: \"QueueItem\"\n{frontmatter_body}---\n\nbody\n")

    def ticket(self, source_line, criteria=True):
        text = f"# T-1: Thing\n\n{source_line}\n\n"
        if criteria:
            text += f"## Acceptance Criteria\n\n- {CRITERION_TEXT}\n"
        path = self.folder / "00-ticket.md"
        path.write_text(text)
        return path

    def test_a_ticket_copied_from_a_queue_item_a_session_wrote_is_session_owned(self):
        self.queue_item('generated: {"by": "claude-code/x", "at": "2026-11-01"}\n')
        owner = plan_format.criteria_owner(self.ticket("Source: ~/agent-evals/queue/item.md"))

        self.assertEqual(owner["owner"], plan_format.CRITERIA_OWNER_SESSION)
        self.assertEqual(owner["rule"], plan_format.CRITERIA_OWNER_RULES[plan_format.CRITERIA_OWNER_SESSION])
        self.assertEqual(owner["source"], "~/agent-evals/queue/item.md")

    def test_a_crlf_queue_file_a_session_wrote_is_session_owned(self):
        crlf_text = ('---\r\ntype: "QueueItem"\r\n'
                     'generated: {"by": "claude-code/x", "at": "2026-11-01"}\r\n---\r\n\r\nbody\r\n')
        (self.queue_dir / "item.md").write_bytes(crlf_text.encode())
        owner = plan_format.criteria_owner(self.ticket("Source: ~/agent-evals/queue/item.md"))

        self.assertEqual(owner["owner"], plan_format.CRITERIA_OWNER_SESSION)

    def test_markdown_marks_and_trailing_text_on_the_source_line_are_allowed(self):
        self.queue_item('generated: {"by": "process:nightly", "at": "2026-11-01"}\n')
        owner = plan_format.criteria_owner(self.ticket("**Source:** `~/agent-evals/queue/item.md` (copied)"))

        self.assertEqual(owner["owner"], plan_format.CRITERIA_OWNER_SESSION)

    def test_a_ticket_that_is_not_a_queue_item_takes_its_owner_from_the_source_line(self):
        self.queue_item('generated: {"by": "claude-code/x", "at": "2026-11-01"}\n')
        own_frontmatter = '---\ntype: "Plan"\ngenerated: {"by": "human:x", "at": "2026-11-01"}\n---\n\n'
        ticket_path = self.ticket("Source: ~/agent-evals/queue/item.md")
        ticket_path.write_text(own_frontmatter + ticket_path.read_text())
        owner = plan_format.criteria_owner(ticket_path)

        self.assertEqual(owner["owner"], plan_format.CRITERIA_OWNER_SESSION)

    def test_a_queue_item_a_human_wrote_is_user_owned(self):
        self.queue_item('generated: {"by": "human:x", "at": "2026-11-01"}\n')
        owner = plan_format.criteria_owner(self.ticket("Source: ~/agent-evals/queue/item.md"))

        self.assertEqual(owner["owner"], plan_format.CRITERIA_OWNER_USER)

    def test_a_missing_queue_file_raises_and_names_it(self):
        ticket = self.ticket("Source: ~/agent-evals/queue/missing.md")

        with self.assertRaises(plan_format.PlanFormatError) as raised:
            plan_format.criteria_owner(ticket)
        self.assertIn(f"{ticket}:3:", str(raised.exception))
        self.assertIn("queue/missing.md", str(raised.exception))

    def test_a_queue_file_with_no_generated_key_raises_and_names_it(self):
        self.queue_item('kind: "chore"\n')
        ticket = self.ticket("Source: ~/agent-evals/queue/item.md")

        with self.assertRaises(plan_format.PlanFormatError) as raised:
            plan_format.criteria_owner(ticket)
        self.assertIn("queue/item.md", str(raised.exception))
        self.assertIn("generated:", str(raised.exception))

    def test_a_queue_file_whose_generated_value_has_no_readable_by_raises_and_names_it(self):
        cases = {
            "no frontmatter": None,
            "generated is not JSON": 'generated: not json\n',
            "generated is not an object": 'generated: ["claude-code/x"]\n',
            "by missing": 'generated: {"at": "2026-11-01"}\n',
            "by empty": 'generated: {"by": "  ", "at": "2026-11-01"}\n',
            "by not a string": 'generated: {"by": 7}\n',
        }
        for label, frontmatter_body in cases.items():
            with self.subTest(label):
                if frontmatter_body is None:
                    (self.queue_dir / "item.md").write_text("body only\n")
                else:
                    self.queue_item(frontmatter_body)
                ticket = self.ticket("Source: ~/agent-evals/queue/item.md")

                with self.assertRaises(plan_format.PlanFormatError) as raised:
                    plan_format.criteria_owner(ticket)
                self.assertIn("queue/item.md", str(raised.exception))
                self.assertIn(f"{ticket}:3:", str(raised.exception))

    def test_a_queue_source_that_is_not_the_queue_form_raises(self):
        for source in ("~/agent-evals/queue/Bad_Slug.md", "~/agent-evals/queue/sub/x.md"):
            with self.subTest(source):
                ticket = self.ticket(f"Source: {source}")

                with self.assertRaises(plan_format.PlanFormatError) as raised:
                    plan_format.criteria_owner(ticket)
                self.assertIn("not the queue form", str(raised.exception))

    def test_the_human_check_is_the_exact_prefix_of_the_stripped_author(self):
        cases = {"humanoid": plan_format.CRITERIA_OWNER_SESSION, " human:x": plan_format.CRITERIA_OWNER_USER}
        for author, expected in cases.items():
            with self.subTest(author):
                self.queue_item(f'generated: {{"by": "{author}", "at": "2026-11-01"}}\n')
                owner = plan_format.criteria_owner(self.ticket("Source: ~/agent-evals/queue/item.md"))

                self.assertEqual(owner["owner"], expected)

    def test_a_queue_item_takes_its_own_generated_by_over_a_source_line(self):
        self.queue_item('generated: {"by": "claude-code/x", "at": "2026-11-01"}\n')
        own_item = self.folder / "own.md"
        own_item.write_text('---\ntype: "QueueItem"\ngenerated: {"by": "human:x", "at": "2026-11-01"}\n---\n\n'
                            "Source: ~/agent-evals/queue/item.md\n")

        owner = plan_format.criteria_owner(own_item)

        self.assertEqual(owner["owner"], plan_format.CRITERIA_OWNER_USER)
        self.assertIsNone(owner["source"])

    def test_a_human_item_named_after_a_session_item_keeps_the_user_as_owner(self):
        self.queue_item('generated: {"by": "claude-code/x", "at": "2026-11-01"}\n', slug="session-item")
        self.queue_item('generated: {"by": "human:x", "at": "2026-11-01"}\n', slug="human-item")
        ticket = self.ticket("Source: ~/agent-evals/queue/session-item.md\nSource: ~/agent-evals/queue/human-item.md")

        owner = plan_format.criteria_owner(ticket)

        self.assertEqual(owner["owner"], plan_format.CRITERIA_OWNER_USER)
        self.assertEqual(owner["source"], "~/agent-evals/queue/human-item.md")

    def test_a_later_queue_source_line_that_names_no_item_is_an_error(self):
        self.queue_item('generated: {"by": "human:x", "at": "2026-11-01"}\n')
        ticket = self.ticket("Source: ~/agent-evals/queue/item.md\nSource: ~/agent-evals/queue/missing.md")

        with self.assertRaisesRegex(plan_format.PlanFormatError, r"00-ticket\.md:4: queue file .*missing\.md"):
            plan_format.criteria_owner(ticket)

    def test_an_unquoted_queue_item_type_is_read_as_a_queue_item(self):
        own_item = self.folder / "own.md"
        own_item.write_text('---\ntype: QueueItem\ngenerated: {"by": "claude-code/x", "at": "2026-11-01"}\n---\n\n'
                            "body\n")

        owner = plan_format.criteria_owner(own_item)

        self.assertEqual(owner["owner"], plan_format.CRITERIA_OWNER_SESSION)

    def test_a_non_queue_source_line_before_the_queue_one_is_skipped(self):
        self.queue_item('generated: {"by": "claude-code/x", "at": "2026-11-01"}\n')
        owner = plan_format.criteria_owner(
            self.ticket("Source: user\nSource: ~/agent-evals/queue/item.md"))

        self.assertEqual(owner["owner"], plan_format.CRITERIA_OWNER_SESSION)
        self.assertEqual(owner["source"], "~/agent-evals/queue/item.md")

    def test_a_pasted_brief_lane_ticket_with_one_source_line_per_item_is_session_owned(self):
        # The ticket mirrors the real pasted-brief lane ticket shape: one Source line per queue item, each item
        # pasted verbatim under its own heading.
        self.queue_item('generated: {"by": "claude-code/x", "at": "2026-11-01"}\n', slug="a")
        self.queue_item('generated: {"by": "claude-code/x", "at": "2026-11-01"}\n', slug="b")
        pasted_item = '---\ntype: "QueueItem"\ngenerated: {"by": "human:x", "at": "2026-11-01"}\n---\n'
        ticket = self.folder / "00-ticket.md"
        ticket.write_text(
            "# Lane brief: x\n\n"
            "Source: ~/agent-evals/queue/a.md\n"
            "Source: ~/agent-evals/queue/b.md\n\n"
            "## Brief (verbatim)\n\n"
            "Do items a and b.\n"
            "git -C ~/agent-evals show origin/bench-base:queue/a.md\n\n"
            f"## Queue item 1 (verbatim)\n\n{pasted_item}\n## Done when\n\n- {CRITERION_TEXT}\n\n"
            f"## Queue item 2 (verbatim)\n\n{pasted_item}\n## Done when\n\n- {CRITERION_TEXT}\n")

        owner = plan_format.criteria_owner(ticket)

        self.assertEqual(owner["owner"], plan_format.CRITERIA_OWNER_SESSION)
        self.assertEqual(owner["source"], "~/agent-evals/queue/a.md")

    def test_a_source_outside_the_queue_folder_never_changes_the_owner(self):
        owner = plan_format.criteria_owner(self.ticket("Source: product-specs/a.md"))

        self.assertEqual(owner["owner"], plan_format.CRITERIA_OWNER_USER)

    def test_a_ticket_with_no_criteria_heading_is_plan_owned(self):
        owner = plan_format.criteria_owner(self.ticket("Source: user, 2026-11-01", criteria=False))

        self.assertEqual(owner["owner"], plan_format.CRITERIA_OWNER_PLAN)

    def test_a_ticket_with_a_misnamed_criteria_heading_still_raises(self):
        ticket = self.folder / "00-ticket.md"
        ticket.write_text("# T-1\n\n## Acceptance notes\n\n- x\n")

        with self.assertRaises(plan_format.PlanFormatError):
            plan_format.criteria_owner(ticket)

    def test_no_ticket_beside_the_plan_gives_user_with_no_ticket(self):
        owner = plan_format.plan_criteria_owner(self.folder / "spec.md")

        self.assertEqual(owner["owner"], plan_format.CRITERIA_OWNER_USER)
        self.assertIsNone(owner["ticket"])

    def test_no_ticket_and_a_criteria_file_beside_a_spec_md_gives_user(self):
        (self.folder / "acceptance-criteria.md").write_text("- **AC1** — x\n")

        owner = plan_format.plan_criteria_owner(self.folder / "spec.md")

        self.assertEqual(owner["owner"], plan_format.CRITERIA_OWNER_USER)

    def test_no_ticket_and_no_criteria_file_beside_plan_md_gives_user(self):
        owner = plan_format.plan_criteria_owner(self.folder / "plan.md")

        self.assertEqual(owner["owner"], plan_format.CRITERIA_OWNER_USER)

    def test_no_ticket_but_a_criteria_file_beside_the_plan_gives_plan_with_no_ticket(self):
        (self.folder / "acceptance-criteria.md").write_text("- **AC1** — x\n")
        (self.folder / "plan.md").write_text("# Plan\n")

        owner = plan_format.plan_criteria_owner(self.folder / "plan.md")

        self.assertEqual(owner["owner"], plan_format.CRITERIA_OWNER_PLAN)
        self.assertIsNone(owner["ticket"])

    def test_a_criteria_file_with_no_plan_file_gives_user(self):
        (self.folder / "acceptance-criteria.md").write_text("- **AC1** — x\n")

        owner = plan_format.plan_criteria_owner(self.folder / "plan.md")

        self.assertEqual(owner["owner"], plan_format.CRITERIA_OWNER_USER)

    def test_several_tickets_beside_the_plan_raise_naming_the_folder_and_the_files(self):
        (self.folder / "A-00-ticket.md").write_text("# T-1\n")
        (self.folder / "B-00-ticket.md").write_text("# T-2\n")

        with self.assertRaises(plan_format.PlanFormatError) as raised:
            plan_format.ticket_beside(self.folder / "spec.md")

        message = str(raised.exception)
        self.assertIn(str(self.folder), message)
        self.assertIn("A-00-ticket.md", message)
        self.assertIn("B-00-ticket.md", message)

    def test_the_exact_ticket_wins_over_a_prefixed_one_beside_the_plan(self):
        (self.folder / "00-ticket.md").write_text("# T-1\n")
        (self.folder / "A-00-ticket.md").write_text("# T-2\n")

        self.assertEqual(plan_format.ticket_beside(self.folder / "spec.md"), self.folder / "00-ticket.md")

    def test_no_ticket_beside_the_plan_still_gives_none(self):
        self.assertIsNone(plan_format.ticket_beside(self.folder / "spec.md"))

    def test_spec_ac_failures_gives_an_error_row_when_several_tickets_sit_beside_the_spec(self):
        (self.folder / "A-00-ticket.md").write_text("# T-1\n")
        (self.folder / "B-00-ticket.md").write_text("# T-2\n")
        spec = self.folder / "spec.md"
        spec.write_text("# Plan\n")

        failures = plan_format.spec_ac_failures(spec)

        self.assertEqual(len(failures), 1)
        self.assertIn("B-00-ticket.md", failures[0])

    def test_a_session_owned_reworded_criterion_with_a_ruling_line_passes_drift(self):
        failures = plan_format.ac_drift_failures(
            f"## Acceptance Criteria\n\n- {CRITERION_TEXT}\n", CRITERIA_WITH_TICKET_NOT_CARRIED, SPEC_WITH_RULING,
            owner=plan_format.CRITERIA_OWNER_SESSION)

        self.assertEqual(failures, [])

    def test_a_ruling_line_naming_the_criterion_one_way_passes_drift(self):
        by_ticket_number = "# Plan\n\n## Plan Deviations\n\n- 2026-11-10: Ticket #1 reworded. The session ruled it.\n"
        by_quoted_text = (
            f'# Plan\n\n## Plan Deviations\n\n- 2026-11-10: "{CRITERION_TEXT}" reworded. The session ruled it.\n')
        for label, spec in (("ticket number", by_ticket_number), ("quoted text", by_quoted_text)):
            with self.subTest(label):
                failures = plan_format.ac_drift_failures(
                    f"## Acceptance Criteria\n\n- {CRITERION_TEXT}\n", CRITERIA_WITH_TICKET_NOT_CARRIED, spec,
                    owner=plan_format.CRITERIA_OWNER_SESSION)

                self.assertEqual(failures, [])

    def test_the_same_ruling_line_on_a_user_owned_ticket_still_fails(self):
        failures = plan_format.ac_drift_failures(
            f"## Acceptance Criteria\n\n- {CRITERION_TEXT}\n", CRITERIA_WITH_TICKET_NOT_CARRIED, SPEC_WITH_RULING,
            owner=plan_format.CRITERIA_OWNER_USER)

        self.assertEqual(len(failures), 1)
        self.assertIn("no AC in the criteria file carries this wording and no sign-off names it. Copy it verbatim "
                      "into one AC, or record the user's sign-off (who and when) naming it", failures[0])
        self.assertNotIn("ruling", failures[0])

    def test_a_session_owned_reworded_criterion_without_a_ruling_asks_for_the_sessions_ruling(self):
        failures = plan_format.ac_drift_failures(
            f"## Acceptance Criteria\n\n- {CRITERION_TEXT}\n", CRITERIA_WITH_TICKET_NOT_CARRIED, "# Plan\n",
            owner=plan_format.CRITERIA_OWNER_SESSION)

        self.assertEqual(len(failures), 1)
        self.assertIn("add a line under `## Plan Deviations` that holds `ruling` and names `Ticket #1`", failures[0])
        self.assertNotIn("--by session", failures[0])

    def test_a_sign_off_line_naming_the_criterion_still_passes_on_a_session_owned_ticket(self):
        spec = f'# Plan\n\n## Plan Deviations\n\n- 2026-11-10: Ticket #1 "{CRITERION_TEXT}" reworded; sign-off by x.\n'
        failures = plan_format.ac_drift_failures(
            f"## Acceptance Criteria\n\n- {CRITERION_TEXT}\n", CRITERIA_WITH_TICKET_NOT_CARRIED, spec,
            owner=plan_format.CRITERIA_OWNER_SESSION)

        self.assertEqual(failures, [])

    def test_a_ruled_line_that_names_no_criterion_does_not_clear_session_owned_drift(self):
        spec = "# Plan\n\n## Plan Deviations\n\n- 2026-11-10: Something else was ruled on.\n"
        failures = plan_format.ac_drift_failures(
            f"## Acceptance Criteria\n\n- {CRITERION_TEXT}\n", CRITERIA_WITH_TICKET_NOT_CARRIED, spec,
            owner=plan_format.CRITERIA_OWNER_SESSION)

        self.assertEqual(len(failures), 1)

    def test_spec_ac_failures_reads_the_owner_of_the_ticket_beside_the_spec(self):
        self.queue_item('generated: {"by": "claude-code/x", "at": "2026-11-01"}\n')
        self.ticket("Source: ~/agent-evals/queue/item.md")
        (self.folder / "acceptance-criteria.md").write_text(CRITERIA_WITH_TICKET_NOT_CARRIED)
        spec = self.folder / "spec.md"
        spec.write_text(SPEC_WITH_RULING)

        self.assertEqual(plan_format.spec_ac_failures(spec), [])


STANDING_LINE = ('Standing ruling by Pat at 2026-11-19: every criterion reword follows one rule covers: rewords')
OWNER_LINES_LINE = ("Standing ruling by the orchestrating session at 2026-11-22: owner lines in the scripts "
                    "CLAUDE.md need no ask covers: owner-lines")
CRITERIA_NAMING_TICKET = ("# Acceptance Criteria\n\n- **AC1** — The cache may reuse a stored value (Ticket #1, "
                          "reworded)\n")
REWORD_IMPACT = ("PLAN-IMPACT:\n  assumed: AC1 as worded\n  found: the cache may reuse\n"
                 "  kind: reword\n  acceptance_criteria: AC1\n  cause: plan")


class StandingRulingTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = pathlib.Path(folder.name)
        self.plan = self.folder / "plan.md"

    def test_a_well_formed_line_in_plan_deviations_parses(self):
        self.plan.write_text(f"# Plan\n\n## Plan Deviations\n\n- {STANDING_LINE}\n")

        rulings = standing_rulings.standing_rulings(self.plan)

        self.assertEqual(rulings, [{"who": "Pat", "at": "2026-11-19",
                                    "summary": "every criterion reword follows one rule", "covers": "rewords"}])

    def test_a_well_formed_line_in_the_decision_log_beside_the_plan_parses(self):
        self.plan.write_text("# Plan\n")
        (self.folder / "03-decisions.md").write_text(f"# Decisions\n\n{STANDING_LINE}\n")

        self.assertEqual(len(standing_rulings.standing_rulings(self.plan)), 1)

    def test_a_standing_line_outside_plan_deviations_is_not_read(self):
        self.plan.write_text(f"# Plan\n\n{STANDING_LINE}\n")

        self.assertEqual(standing_rulings.standing_rulings(self.plan), [])

    def test_an_owner_lines_line_parses_and_only_the_owner_line_reader_returns_it(self):
        self.plan.write_text("# Plan\n")
        (self.folder / "03-decisions.md").write_text(f"# Decisions\n\n{OWNER_LINES_LINE}\n")

        rulings = standing_rulings.standing_rulings(self.plan)

        self.assertEqual(rulings[0]["covers"], "owner-lines")
        owner_ruling = standing_rulings.first_ruling_covering(self.plan, standing_rulings.COVERS_OWNER_LINES)
        self.assertEqual(owner_ruling, rulings[0])
        self.assertIsNone(standing_rulings.reword_ruling(self.plan))

    def test_a_rewords_line_alone_gives_no_owner_line_ruling(self):
        self.plan.write_text(f"# Plan\n\n## Plan Deviations\n\n- {STANDING_LINE}\n")

        owner_ruling = standing_rulings.first_ruling_covering(self.plan, standing_rulings.COVERS_OWNER_LINES)
        self.assertIsNone(owner_ruling)

    def test_with_both_lines_each_reader_returns_its_own(self):
        self.plan.write_text(f"# Plan\n\n## Plan Deviations\n\n- {OWNER_LINES_LINE}\n- {STANDING_LINE}\n")

        owner_ruling = standing_rulings.first_ruling_covering(self.plan, standing_rulings.COVERS_OWNER_LINES)
        self.assertEqual(owner_ruling["covers"], "owner-lines")
        self.assertEqual(standing_rulings.reword_ruling(self.plan)["covers"], "rewords")

    def test_a_malformed_line_raises_naming_the_file_the_line_and_the_form(self):
        malformed = {
            "covers cuts": 'Standing ruling by Pat at 2026-11-19: x covers: cuts',
            "no summary": "Standing ruling by Pat at 2026-11-19 covers: rewords",
            "quoted words": 'Standing ruling by Pat at 2026-11-19: "x" covers: rewords',
            "bad date": 'Standing ruling by Pat at yesterday: x covers: rewords',
        }
        for label, line in malformed.items():
            with self.subTest(label):
                self.plan.write_text(f"# Plan\n\n## Plan Deviations\n\n{line}\n")

                with self.assertRaises(plan_format.PlanFormatError) as raised:
                    standing_rulings.standing_rulings(self.plan)

                message = str(raised.exception)
                self.assertIn(f"{self.plan}:5:", message)
                self.assertIn(standing_rulings.STANDING_RULING_FORM, message)

    def test_a_reword_whose_ac_names_the_ticket_criterion_passes_drift_only_with_the_ruling(self):
        ticket = f"## Acceptance Criteria\n\n- {CRITERION_TEXT}\n"

        without = plan_format.ac_drift_failures(ticket, CRITERIA_NAMING_TICKET, "# Plan\n")
        with_ruling = plan_format.ac_drift_failures(ticket, CRITERIA_NAMING_TICKET, "# Plan\n", rewords_ruled=True)

        self.assertEqual(len(without), 1)
        self.assertEqual(with_ruling, [])

    def test_a_criterion_no_ac_names_still_fails_with_the_ruling(self):
        ticket = f"## Acceptance Criteria\n\n- {CRITERION_TEXT}\n"

        failures = plan_format.ac_drift_failures(ticket, CRITERIA_WITH_TICKET_NOT_CARRIED, "# Plan\n",
                                                 rewords_ruled=True)

        self.assertEqual(len(failures), 1)

    def test_a_note_line_that_names_the_ticket_is_no_ac_and_the_cut_still_fails_with_the_ruling(self):
        ticket = f"## Acceptance Criteria\n\n- {CRITERION_TEXT}\n"
        criteria = "# Acceptance Criteria\n\n- **AC1** — Something else\n\nNote: Ticket #1 cut, out of scope\n"

        failures = plan_format.ac_drift_failures(ticket, criteria, "# Plan\n", rewords_ruled=True)

        self.assertEqual(len(failures), 1)

    def test_a_malformed_line_in_the_decision_log_raises_naming_that_file_and_line(self):
        self.plan.write_text(f"# Plan\n\n## Plan Deviations\n\n- {STANDING_LINE}\n")
        decisions = self.folder / "03-decisions.md"
        decisions.write_text('# Decisions\n\nStanding ruling by Pat at yesterday: x covers: rewords\n')

        with self.assertRaises(plan_format.PlanFormatError) as raised:
            standing_rulings.standing_rulings(self.plan)

        self.assertIn(f"{decisions}:3:", str(raised.exception))

    def test_the_impact_kind_reads_reword_only_when_every_impact_says_so(self):
        cut = REWORD_IMPACT.replace("kind: reword", "kind: cut")
        no_id = REWORD_IMPACT.replace("AC1", "none")
        no_kind = "PLAN-IMPACT:\n  acceptance_criteria: AC1"
        kindless = "PLAN-IMPACT:\n  acceptance_criteria: AC2\n  cause: plan"
        cases = {"reword": (REWORD_IMPACT, True), "cut": (cut, False), "no kind": (no_kind, False),
                 "no id": (no_id, False),
                 "reword and cut": (f"{REWORD_IMPACT}\n\n{cut}", False),
                 "reword and no kind": (f"{REWORD_IMPACT}\n\n{kindless}", False),
                 "two rewords": (f"{REWORD_IMPACT}\n\n{REWORD_IMPACT.replace('AC1', 'AC2')}", True)}
        for label, (text, expected) in cases.items():
            with self.subTest(label):
                self.assertEqual(standing_rulings.impact_rewords_criterion(text), expected)


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


class AcQuotesTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.folder = pathlib.Path(self.dir.name)
        self.plan = self.folder / "spec.md"

    def test_ac_quotes_takes_double_and_curly_quotes_and_spaced_backticks(self):
        text = 'say "limit = 3" and “a b” and `x y` and `solo` and "" and "  " and "limit = 3"'

        self.assertEqual(plan_format.ac_quotes(text), ["limit = 3", "a b", "x y"])

    def test_plan_ac_quotes_reads_the_criteria_file_and_the_ticket_beside_the_plan(self):
        (self.folder / "acceptance-criteria.md").write_text('- **AC1** — keep "limit = 3" as it is\n')
        ticket_text = '# T\n\n## Acceptance Criteria\n\n- says "limit = 3" and "other text"\n'
        (self.folder / "00-ticket.md").write_text(ticket_text)

        quotes = plan_format.plan_ac_quotes(self.plan)

        self.assertEqual(quotes, {"limit = 3": ["AC1", "Ticket #1"], "other text": ["Ticket #1"]})

    def test_plan_ac_quotes_with_no_criteria_file_and_no_ticket_is_empty(self):
        self.assertEqual(plan_format.plan_ac_quotes(self.plan), {})

    def test_plan_ac_quotes_ticket_with_no_criteria_heading_adds_nothing(self):
        (self.folder / "00-ticket.md").write_text('# T\n\njust prose with "some quoted text"\n')

        self.assertEqual(plan_format.plan_ac_quotes(self.plan), {})

    def test_plan_ac_quotes_duplicate_ac_id_raises_an_error_naming_the_criteria_file(self):
        criteria_path = self.folder / "acceptance-criteria.md"
        criteria_path.write_text("- **AC1** — one\n- **AC1** — two\n")

        with self.assertRaises(plan_format.PlanFormatError) as raised:
            plan_format.plan_ac_quotes(self.plan)

        self.assertTrue(str(raised.exception).startswith(f"{criteria_path}:2:"), str(raised.exception))

    @unittest.skipIf(os.geteuid() == 0, "root reads any file")
    def test_plan_ac_quotes_unreadable_criteria_file_raises_an_oserror_naming_the_file(self):
        criteria_path = self.folder / "acceptance-criteria.md"
        criteria_path.write_text("- **AC1** — one\n")
        criteria_path.chmod(0)

        with self.assertRaises(OSError) as raised:
            plan_format.plan_ac_quotes(self.plan)

        self.assertEqual(raised.exception.filename, str(criteria_path))

    def test_plan_ac_quotes_ticket_with_a_bad_criteria_heading_raises_an_error_naming_the_ticket(self):
        ticket_path = self.folder / "00-ticket.md"
        ticket_path.write_text("# T\n\n## Acceptance Criterion Notes\n\n- says \"x y\"\n")

        with self.assertRaises(plan_format.PlanFormatError) as raised:
            plan_format.plan_ac_quotes(self.plan)

        self.assertTrue(str(raised.exception).startswith(f"{ticket_path}:"), str(raised.exception))


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

    def test_every_real_plan_folder_s_ac_quotes_parse(self):
        paths = sorted(glob.glob(str(pathlib.Path.home() / "dev" / "*" / "docs" / "plans" / "*" / "spec.md")))
        if not paths:
            self.skipTest("no real plan folders on this machine")
        parsed = span_count = 0
        for path in paths:
            with self.subTest(path=path):
                span_count += len(plan_format.plan_ac_quotes(pathlib.Path(path)))
                parsed += 1
        print(f"parsed {parsed} of {len(paths)} real plan folders, {span_count} quoted spans", file=sys.stderr)

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

    def test_an_item_the_coder_never_runs_gives_no_variables(self):
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

    def test_an_agent_run_item_is_tagged_in_any_case_with_or_without_a_bold_label(self):
        for item in ("- [ ] **Agent-run**: time the import on the real data",
                     "- [ ] Agent-run: run it on the live home", "- [x] agent-run: done", "- [ ] **AGENT-RUN**: x"):
            with self.subTest(item=item):
                self.assertEqual("agent-run", plan_format.deferred_verification_tag(item))
                self.assertTrue(plan_format.runs_no_command(item))

    def test_an_agent_run_item_gives_no_gate_variables(self):
        plan = "#### Automated Verification:\n\n- [ ] **Agent-run**: time `SLOW=1 make import`\n"

        self.assertEqual([], plan_format.gate_env(plan))

    def test_an_item_with_a_command_runs_it_even_when_it_mentions_ci_or_n_a_later(self):
        for item in ("- [ ] **Unit**: `npm test`, not CI-verified", "- [ ] **Check**: `make check` (N/A on mac)",
                     "- [ ] `RUN x`"):
            with self.subTest(item=item):
                self.assertFalse(plan_format.runs_no_command(item))

    def test_the_item_text_is_the_line_without_its_box_and_edge_spaces(self):
        self.assertEqual("**Unit**: `npm test`", plan_format.automated_item_text("  - [ ] **Unit**: `npm test`  "))
        self.assertEqual("done", plan_format.automated_item_text("- [x]   done"))
        self.assertEqual("", plan_format.automated_item_text("- [ ]"))


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
        self.assertEqual("/close-branch",
                         plan_format.closing_skill("Close pass — /close-branch parallel review, one fix (risk: high)"))
        self.assertIsNone(plan_format.closing_skill("Verify pass for the orders API"))
        self.assertIsNone(plan_format.closing_skill("Close pass for the orders API"))
        self.assertIsNone(plan_format.closing_skill("Build it"))

    def test_the_closing_phases_are_recognised_and_need_no_section(self):
        closing = [(entry["number"], entry["closing"]) for entry in self.entries()]
        self.assertEqual([("1", None), ("2", None), ("3", "/refactor +deep"), ("4", "/verify-branch"), ("5", None)],
                         closing)

    def test_phase_text_is_the_section_or_none(self):
        lines = CLOSING_PLAN.split("\n")
        self.assertEqual("## Phase 1: Build\n\nbuild text\n", plan_format.phase_text(lines, "1"))
        self.assertIsNone(plan_format.phase_text(lines, "4"))

    def test_the_phase_line_range_counts_from_1_and_matches_the_phase_text(self):
        lines = CLOSING_PLAN.split("\n")
        first, last = plan_format.phase_line_range(lines, "1")
        self.assertEqual("## Phase 1: Build", lines[first - 1])
        self.assertEqual(plan_format.phase_text(lines, "1"), "\n".join(lines[first - 1:last]))
        self.assertIsNone(plan_format.phase_line_range(lines, "4"))

    def test_the_plan_folder_is_the_plans_own_folder_and_no_folder_for_a_plan_with_none(self):
        self.assertEqual("docs/plans/p/", plan_format.plan_folder("docs/plans/p/spec.md"))
        for plan in ("", "-", "spec.md", "/abs/docs/plans/p/spec.md", "docs/foo.md", "docs/plans/foo.md"):
            with self.subTest(plan=plan):
                self.assertEqual("", plan_format.plan_folder(plan))
                self.assertEqual("", plan_format.plan_folder_exclude(plan))
        self.assertEqual(":(exclude)docs/plans/p/", plan_format.plan_folder_exclude("docs/plans/p/spec.md"))

    def test_paths_under_the_plan_folder_are_left_out_in_the_same_shape(self):
        plan = "docs/plans/p/spec.md"
        paths = ["docs/plans/p/research/a.md", "docs/plans/p/spec.md", "docs/plans/p2/spec.md", "src/a.py"]
        self.assertEqual(["docs/plans/p2/spec.md", "src/a.py"], plan_format.outside_plan_folder(paths, plan))
        entries = dict.fromkeys(paths, "entry")
        self.assertEqual({"docs/plans/p2/spec.md": "entry", "src/a.py": "entry"},
                         plan_format.outside_plan_folder(entries, plan))
        self.assertEqual(paths, plan_format.outside_plan_folder(paths, "-"))

    def test_the_failure_rows_name_the_plan_line_kind_and_detail(self):
        plan = {"failures": [{"line": 4, "kind": "duplicate-id", "detail": "Phase 1 twice"}]}
        self.assertEqual(["spec.md:4: duplicate-id: Phase 1 twice"], plan_format.plan_failure_rows(plan, "spec.md"))


class PlanFileEditTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.plan_path = pathlib.Path(folder.name) / "spec.md"
        self.plan_path.write_text(CLOSING_PLAN)

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

    def test_a_deviation_for_a_plan_folder_goes_to_the_plan_file_inside_it(self):
        folder = self.plan_path.parent / "plan-folder"
        folder.mkdir()
        plan_file = folder / "plan.md"
        plan_file.write_text(CLOSING_PLAN)
        plan_format.append_deviation(folder, ["- folder note"])
        self.plan_path.write_text(CLOSING_PLAN)
        plan_format.append_deviation(self.plan_path, ["- folder note"])
        self.assertEqual(self.plan_path.read_text(), plan_file.read_text())

    def test_a_deviation_for_a_folder_with_no_plan_file_raises_the_plan_error(self):
        folder = self.plan_path.parent / "empty-folder"
        folder.mkdir()
        with self.assertRaisesRegex(plan_format.PlanFormatError, "empty-folder"):
            plan_format.append_deviation(folder, ["- note"])

    def test_a_ruling_entry_names_the_phase_decision_owner_ruling_and_disagreement(self):
        entry = plan_format.ruling_deviation("2", "Adopt plan change", "Pat Signer", "2026-10-25 09:30",
                                             "use the  new\ntable", "assumed: one table\nfound: two")
        self.assertEqual(["- 2026-10-25 (Phase 2): Adopt plan change. Ruled by Pat Signer at 2026-10-25 09:30.", "",
                          "  The ruling: use the new table", "", "  The disagreement:", "  assumed: one table",
                          "  found: two"], entry)

    def test_the_resolved_texts_read_the_same_from_the_one_line_and_the_block_handoff(self):
        carried = f"  {plan_format.CARRIED_FINDINGS_KEY}  # open\n    - finding one\n    - finding two\n"
        one_line = "  plan_impact: RESOLVED - Adopt.\n" + carried
        block = ("RESOLVED: the user ruled. Review the code against the ruling.\nDecision: Adopt\nThe ruling:\n"
                 "  do it\nPLAN-IMPACT:\n  found: a\n  found: b")
        block_form = "  plan_impact: |\n" + "".join(f"    {line}\n" for line in block.splitlines()) + carried

        self.assertEqual(["plan_impact: RESOLVED - Adopt.", "finding one", "finding two"],
                         plan_format.resolved_plan_texts(one_line))
        self.assertEqual(["finding one", "finding two"], plan_format.resolved_plan_texts(block_form)[-2:])
        self.assertIn("found: a found: b", plan_format.resolved_plan_texts(block_form))
        self.assertEqual([], plan_format.resolved_plan_texts("  plan_impact: none\n" + carried))

    def test_the_resolved_texts_keep_the_text_on_the_plan_impact_header_line(self):
        block = "RESOLVED: the user ruled.\nPLAN-IMPACT: found: the queue is at-most-once\n  changes: the retry phase"
        handoff = "  plan_impact: |\n" + "".join(f"    {line}\n" for line in block.splitlines())

        self.assertIn("found: the queue is at-most-once changes: the retry phase",
                      plan_format.resolved_plan_texts(handoff))

    def test_the_resolved_texts_read_a_plan_impact_header_that_follows_a_location(self):
        block = ("RESOLVED: the user ruled.\napp.py:14 [docs] — PLAN-IMPACT: found: the queue is at-most-once\n"
                 "  changes: the retry phase")
        handoff = "  plan_impact: |\n" + "".join(f"    {line}\n" for line in block.splitlines())

        self.assertIn("found: the queue is at-most-once changes: the retry phase",
                      plan_format.resolved_plan_texts(handoff))

    def test_the_ruled_impact_text_ends_at_a_carried_findings_line_at_the_same_indent(self):
        lines = ["RESOLVED: the user ruled.", "PLAN-IMPACT:", "  found: a", plan_format.CARRIED_FINDINGS_KEY,
                 "  - finding one"]

        self.assertEqual("found: a", plan_format.ruled_impact_text(lines, 0, 0))

    def test_the_resolved_texts_read_a_bold_or_backticked_plan_impact_header(self):
        for header in ("**PLAN-IMPACT:**", "`PLAN-IMPACT:`", "- **PLAN-IMPACT**:"):
            with self.subTest(header):
                block = f"RESOLVED: the user ruled.\n{header}\n  found: a\n  changes: b"
                handoff = "  plan_impact: |\n" + "".join(f"    {line}\n" for line in block.splitlines())

                self.assertIn("found: a changes: b", plan_format.resolved_plan_texts(handoff))

    def test_a_ruling_entry_with_no_phase_leaves_the_phase_out(self):
        entry = plan_format.ruling_deviation(None, "Keep plan as written", "the session, not the user",
                                             "2026-10-25 09:30", "keep it", "found: two")
        self.assertEqual("- 2026-10-25: Keep plan as written. Ruled by the session, not the user at 2026-10-25 09:30.",
                         entry[0])


class ManualFormatHelpersTest(unittest.TestCase):
    GOOD = ("## Phase 1: a\n\n#### Manual Verification:\n\n- [ ] open it\n\n## Phase 2: b\n\n"
            "#### Manual Verification:\n\n- [ ] read it\n")
    BAD = "## Phase 1: a\n\n#### Manual Verification:\n\n- [ ] open it\n| a | b |\n"

    def test_a_section_that_parses_has_no_failure_message(self):
        self.assertIsNone(plan_format.manual_format_failure(self.GOOD.split("\n"), "spec.md"))

    def test_a_section_that_does_not_parse_gives_the_stop_message_and_the_resume_line(self):
        message = plan_format.manual_format_failure(self.BAD.split("\n"), "spec.md", "Then run resume.")
        self.assertTrue(message.startswith("The plan's Manual Verification section does not parse."))
        self.assertIn("spec.md", message)
        self.assertTrue(message.endswith("\nThen run resume."))
        self.assertFalse(plan_format.manual_format_message("boom").endswith("\n"))

    def test_cited_phases_lists_the_phases_a_phase_reuses_directly_and_through_another(self):
        plan_lines = [
            "## Phase 1: First", "", "Mutants: a, b.", "",
            "## Phase 2: Second", "", "same as Phase 1.", "",
            "## Phase 3: Third", "", "same as Phase 2.", "",
        ]

        cited = plan_format.cited_phases(plan_lines, "3", "\n".join(plan_lines[8:]))

        self.assertEqual([("2", 5, 8), ("1", 1, 4)], cited)


class CriteriaIdsTest(unittest.TestCase):
    def test_ids_come_from_the_acceptance_criteria_line_else_the_bare_ids(self):
        self.assertEqual(plan_format.criteria_ids("x\n  acceptance_criteria: AC2, AC10; cause: plan"),
                         frozenset({"AC2", "AC10"}))
        self.assertEqual(plan_format.criteria_ids("the reworded AC2 and AC3 hold"), frozenset({"AC2", "AC3"}))
        self.assertEqual(plan_format.criteria_ids("acceptance_criteria: none\nAC4 is mentioned"), frozenset())
        self.assertEqual(plan_format.criteria_ids("acceptance_criteria: none\nacceptance_criteria: AC4"),
                         frozenset({"AC4"}))
        self.assertEqual(plan_format.criteria_ids("acceptance_criteria: AC1, AC2\nacceptance_criteria: AC3"),
                         frozenset({"AC1", "AC2", "AC3"}))

    def test_criterion_ids_in_reads_a_bare_upper_case_id_and_skips_names_and_ticket_ids(self):
        text = "AC1 holds: see ac3-evidence.md; ticket AC5 also; test_ac1_x"

        self.assertEqual(plan_format.criterion_ids_in(text), ["AC1"])

    def test_answers_only_names_no_id_for_a_text_without_the_line(self):
        self.assertEqual(plan_format.criteria_ids("the reworded AC2 holds", answers_only=True), frozenset())
        self.assertEqual(plan_format.criteria_ids("acceptance_criteria: AC2", answers_only=True), frozenset({"AC2"}))


RULING_ENTRY = plan_format.ruling_deviation(3, "Keep plan as written", "the session, not the user",
                                            "2026-11-11 03:17", "kept\n  as written", "path:1 the finding")
SIGNOFF_PLAN = "\n".join([
    "# Plan", "", "A sign-off is mentioned here, outside the log.", "", "## Plan Deviations", "",
    *RULING_ENTRY, "",
    "- 2026-11-10: AC1 narrowed. Ruled by the orchestrating session x,",
    "  not the user, 2026-11-10.",
    "- AC5 cut: user sign-off, Brandon, 2026-11-10.",
    "- Rulings by x, 2026-11-13, on the items:", "- an entry with no mark", "", "## Phase 1: x", "",
    "Ruled by nobody here.",
])


class SignoffLinesTest(unittest.TestCase):
    def numbers(self, text):
        return [number for number, _line in signoff_lines.signoff_lines(text)]

    def test_every_entry_form_of_a_deviations_section_is_found_and_other_sections_are_not(self):
        lines = SIGNOFF_PLAN.splitlines()
        entry_start = lines.index(RULING_ENTRY[0]) + 1
        expected = [entry_start, entry_start + 2, entry_start + 7, entry_start + 8, entry_start + 9,
                    entry_start + 10]

        self.assertEqual(self.numbers(SIGNOFF_PLAN), expected)

    def test_the_disagreement_block_of_an_entry_is_not_a_sign_off_line(self):
        found = [line for _number, line in signoff_lines.signoff_lines(SIGNOFF_PLAN)]

        self.assertFalse(any("The disagreement" in line or "path:1" in line for line in found))

    def test_a_text_with_no_deviations_heading_is_read_whole(self):
        self.assertEqual(self.numbers("# Decisions\n\nRuled by the user at 2026-11-11 10:00.\nplain\n"), [3])

    def test_a_plan_md_with_no_deviations_heading_has_no_sign_off_line_even_with_the_word_ruling(self):
        text = "# Plan\n\n## Phase 1: x\n\n- the ruling check runs first\n"

        self.assertEqual([number for number, _line in signoff_lines.signoff_lines(text, "plan.md")], [])

    def test_a_spec_md_with_no_deviations_heading_has_no_sign_off_line_even_with_the_word_sign_off(self):
        text = "# Spec\n\n## Steps\n\n- the user's sign-off is asked for first\n- a ruling is recorded\n"

        self.assertEqual([number for number, _line in signoff_lines.signoff_lines(text, "spec.md")], [])

    def test_eng_spec_prose_notes_yield_no_sign_off_lines(self):
        text = "# Research\n\n- the user's sign-off is asked for first\n- a ruling is recorded\n"

        for name in ("01-questions.md", "02-research.md"):
            found = [number for number, _line in signoff_lines.signoff_lines(text, name)]
            self.assertEqual(found, [], name)

    def test_an_evidence_file_with_no_deviations_heading_is_read_whole(self):
        text = "# Notes\n\nRuled by the user.\n"

        self.assertEqual([number for number, _line in signoff_lines.signoff_lines(text, "evidence.md")], [3])

    def test_an_indented_marker_after_a_blank_line_does_not_mark_the_earlier_bullet(self):
        text = self.deviation_plan("- earlier entry", "", "  Ruled by agent.")

        self.assertEqual(self.numbers(text), [7])

    def test_a_wrapped_marker_under_an_unindented_first_line_is_found_from_that_line(self):
        text = self.deviation_plan("Phase 2: moved the step;", "  decided by the session.")

        self.assertEqual(self.numbers(text), [5, 6])

    def deviation_plan(self, *entry_lines):
        return "\n".join(["# Plan", "", "## Plan Deviations", "", *entry_lines, "", "## Phase 1: x", "", "text"])

    def test_a_wrapped_bullet_with_the_marker_on_the_continuation_is_found_from_its_first_line(self):
        text = self.deviation_plan(
            "- Phase 3 rule: the guard subtracts only the new",
            "  line. Ruled by agent, 2026-11-13.",
            "- plain entry",
        )

        self.assertEqual(self.numbers(text), [5, 6])

    def test_adopted_decided_cut_and_signed_off_forms_are_found(self):
        forms = ["- Phase 1: moved. Adopted by the session, 2026-11-19.",
                 "- Phase 2: kept; decided by the session.",
                 "Phase 3: dropped; decided by the lane session.",
                 "- AC1 cut by the lane session, 2026-11-10.",
                 "- AC2 reworded by the lane session.",
                 "- Brandon Corey signed off the cut, 2026-11-10.",
                 "- Phase 1 ruling (AC1, owner plan, session, 2026-11-13)"]
        for form in forms:
            with self.subTest(form=form):
                self.assertEqual(self.numbers(self.deviation_plan(form)), [5])

    def test_nested_rulings_under_a_rulings_by_header_are_all_found(self):
        text = self.deviation_plan("- Rulings by agent, 2026-11-13, on the items:", "  - Cut the first: reason",
                                   "    wrapped.", "  - Replaced the second.", "- an entry with no mark")

        self.assertEqual(self.numbers(text), [5, 6, 7, 8])

    def test_a_bullet_entry_with_no_marker_is_not_found(self):
        self.assertEqual(self.numbers(self.deviation_plan("- Phase 1: reworded the text.", "  wrapped")), [])

    @unittest.skipUnless(toolkit_paths.REAL_PLANS_ENABLED, toolkit_paths.REAL_PLANS_SKIP_REASON)
    def test_every_marked_deviation_entry_of_the_repos_own_plans_has_its_first_line_found(self):
        plans = sorted(glob.glob(str(REPO_ROOT / "docs" / "plans" / "*" / "plan.md")))
        entries = 0
        for plan in plans:
            text = pathlib.Path(plan).read_text(errors="replace")
            lines = text.splitlines()
            section = script_utils.heading_section_indexes(lines, plan_format.DEVIATIONS_HEADING)
            found = {number for number, _line in signoff_lines.signoff_lines(text)}
            for index in section:
                if not lines[index].startswith("- ") or not signoff_lines.is_signoff_marker(lines[index]):
                    continue
                entries += 1
                with self.subTest(plan=plan, line=index + 1):
                    self.assertIn(index + 1, found)
        self.assertGreater(entries, 0)
        print(f"checked {entries} marked deviation entries of {len(plans)} repo plans", file=sys.stderr)


if __name__ == "__main__":
    unittest.main()
