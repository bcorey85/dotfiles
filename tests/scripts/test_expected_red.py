"""Checks for expected_red.py: a phase's Expected red lines and the files a plan gives only to later phases.

Set EXPECTED_RED_MODULE to run against another copy, such as a staged one."""
import os
import pathlib
import sys
import unittest

import toolkit_paths

MODULE = pathlib.Path(os.environ.get("EXPECTED_RED_MODULE") or toolkit_paths.LIB_DIR / "expected_red.py")
sys.path.insert(0, str(MODULE.parent))
import expected_red  # noqa: E402

QUALITY_CHECK = "ruff check . && pytest -q"
PLAN = """# Plan

## Phase Status

- [ ] Phase 1: Totals (risk: low)
- [ ] Phase 2: Audit (risk: low)
- [ ] Phase 3: Refactor pass - /refactor cleanup sweep (risk: low)

## Phase 1: Totals

**File**: `app/totals.py`
**File**: `app/shared.py`

#### Automated Verification:

- [ ] **Test-verified**: totals pass - `pytest -q tests/test_totals.py`

Expected red: `pytest -q` until Phase 2

## Phase 2: Audit

**File**: `app/audit.py`
**File**: `app/shared.py`

## Phase 3: Refactor pass
"""


def plan_lines(text=PLAN):
    return text.splitlines()


def failure_kinds(text):
    return [failure["kind"] for failure in expected_red.plan_failures(plan_lines(text), QUALITY_CHECK)]


class PlanFailuresTest(unittest.TestCase):
    def test_a_line_in_the_declared_form_that_names_a_later_phase_and_a_check_step_passes(self):
        self.assertEqual([], expected_red.plan_failures(plan_lines(), QUALITY_CHECK))

    def test_each_wrong_line_fails_with_its_own_kind(self):
        line = "Expected red: `pytest -q` until Phase 2"
        cases = [
            ("no backticks", "Expected red: pytest -q until Phase 2", ["expected-red-form"]),
            ("a phase not in Phase Status", "Expected red: `pytest -q` until Phase 7", ["expected-red-unknown-phase"]),
            ("the phase that holds the line", "Expected red: `pytest -q` until Phase 1", ["expected-red-not-later"]),
            ("a command that is no step of the check", "Expected red: `pytest -x` until Phase 2",
             ["expected-red-not-the-check"]),
        ]
        for message, replacement, kinds in cases:
            with self.subTest(message):
                self.assertEqual(kinds, failure_kinds(PLAN.replace(line, replacement)))

    def test_a_target_before_the_holding_phase_fails(self):
        text = PLAN.replace("Expected red: `pytest -q` until Phase 2\n", "")
        text = text.replace("## Phase 3: Refactor pass", "Expected red: `pytest -q` until Phase 1\n\n"
                                                          "## Phase 3: Refactor pass")
        self.assertEqual(["expected-red-not-later"], failure_kinds(text))

    def test_a_line_outside_every_phase_section_fails(self):
        text = PLAN.replace("## Phase Status", "Expected red: `pytest -q` until Phase 2\n\n## Phase Status")
        self.assertEqual(["expected-red-outside-phase"], failure_kinds(text))

    def test_a_repo_with_no_quality_check_fails_the_line(self):
        failures = expected_red.plan_failures(plan_lines(), None)
        self.assertEqual(["expected-red-no-check"], [failure["kind"] for failure in failures])

    def test_a_line_inside_a_fence_is_not_read(self):
        text = PLAN.replace("## Phase 2: Audit", "```\nExpected red: anything\n```\n\n## Phase 2: Audit")
        self.assertEqual([], failure_kinds(text))


class CheckForPhaseTest(unittest.TestCase):
    def test_a_step_named_while_its_phase_is_open_is_left_out_of_the_check(self):
        command, left_out = expected_red.check_for_phase(QUALITY_CHECK, plan_lines(), "1")
        self.assertEqual("ruff check .", command)
        self.assertEqual(["pytest -q"], [entry["command"] for entry in left_out])

    def test_the_whole_check_named_leaves_no_command_and_a_not_run_result(self):
        text = PLAN.replace("`pytest -q` until", f"`{QUALITY_CHECK}` until")
        command, left_out = expected_red.check_for_phase(QUALITY_CHECK, plan_lines(text), "1")
        self.assertIsNone(command)
        self.assertEqual("not run (expected red until Phase 2)", expected_red.not_run_result(left_out))

    def test_two_lines_that_name_every_step_of_the_check_leave_no_command_and_both_entries(self):
        text = PLAN.replace("Expected red: `pytest -q` until Phase 2\n",
                            "Expected red: `pytest -q` until Phase 2\nExpected red: `ruff check .` until Phase 2\n")
        command, left_out = expected_red.check_for_phase(QUALITY_CHECK, plan_lines(text), "1")
        self.assertIsNone(command)
        self.assertEqual(["pytest -q", "ruff check ."], [entry["command"] for entry in left_out])
        self.assertEqual("not run (expected red until Phase 2)", expected_red.not_run_result(left_out))

    def test_once_the_named_phase_is_done_the_check_runs_whole_again(self):
        text = PLAN.replace("- [ ] Phase 2:", "- [x] Phase 2:")
        self.assertEqual((QUALITY_CHECK, []), expected_red.check_for_phase(QUALITY_CHECK, plan_lines(text), "1"))

    def test_another_phase_runs_the_whole_check(self):
        self.assertEqual((QUALITY_CHECK, []), expected_red.check_for_phase(QUALITY_CHECK, plan_lines(), "2"))

    def test_a_plan_with_no_phase_status_and_no_line_runs_the_whole_check(self):
        self.assertEqual((QUALITY_CHECK, []), expected_red.check_for_phase(QUALITY_CHECK, ["# Notes"], "2"))


class LaterPhasePathsTest(unittest.TestCase):
    def test_a_file_only_an_open_later_phase_names_is_closed_and_a_shared_one_stays_open(self):
        self.assertEqual(["app/audit.py"], expected_red.later_phase_paths(plan_lines(), "1"))

    def test_a_done_later_phase_closes_no_file(self):
        text = PLAN.replace("- [ ] Phase 2:", "- [x] Phase 2:")
        self.assertEqual([], expected_red.later_phase_paths(plan_lines(text), "1"))

    def test_a_path_a_later_phase_only_mentions_stays_open(self):
        mention = "**File**: `app/audit.py`\n\nVerify `app/report.py` still loads."
        text = PLAN.replace("**File**: `app/audit.py`", mention)
        self.assertEqual(["app/audit.py"], expected_red.later_phase_paths(plan_lines(text), "1"))

    def test_each_path_of_a_files_list_is_closed_and_a_path_inside_its_text_is_not(self):
        files_list = ("**Files**:\n\n- `app/audit.py`: add the log, calling `app/report.py`.\n"
                      "  - `app/nested.py`: a sub-bullet\n- New: `app/store.py`\n\nAfter `app/after.py`.")
        text = PLAN.replace("**File**: `app/audit.py`", files_list)
        self.assertEqual(["app/audit.py", "app/store.py"], expected_red.later_phase_paths(plan_lines(text), "1"))

    def test_every_path_on_a_files_line_is_closed(self):
        text = PLAN.replace("**File**: `app/audit.py`", "- **Files**: `app/audit.py`, `app/store.py`")
        self.assertEqual(["app/audit.py", "app/store.py"], expected_red.later_phase_paths(plan_lines(text), "1"))

    def test_a_phase_not_in_phase_status_closes_no_file(self):
        self.assertEqual([], expected_red.later_phase_paths(plan_lines(), "9"))


if __name__ == "__main__":
    unittest.main()
