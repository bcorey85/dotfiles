---
type: "Change"
change_type: "changed"
title: "The PLAN-IMPACT criteria rule has one owner per side, and code-reviewer points at the calibration file"
description: "coder-core points at its PLAN-IMPACT findings section for the acceptance_criteria line; code-reviewer drops its blocker sentence, moves its plan-impact line into a Plan impact section, and reads reviewer-calibration's Disposition and Verify the Premise sections once from its preamble; reviewer-calibration names code-reviewer as a reader and carries the optional kind line; the opencode code-reviewer port gets the Plan impact section and reads only Verify the Premise Before Flagging and Disposition (Calibration Anchor and Self-Check Before Reporting are no longer adopted there); the review loop takes a `### Plan impact` line in as an ask, and a `PLAN-IMPACT:` prefix wrapped in backticks or bold, on its own or after a class tag or file:line, now counts as a plan impact."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T20:00:00-06:00"}
seq: 29
kind: "fix"
components: ["skill/coder-core", "agent/code-reviewer", "shared/reviewer-calibration", "script/review-loop", "script/plan-format"]
evidence: ["rule meter", "judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_the_plan_impact_criteria_rule_has_one_owner_per_side"
asked: ""
proof: []
unmeasured: "The coder-core pointer and the build-to-code sentence moved into PLAN-IMPACT findings, the code-reviewer preamble pointer and Plan impact section, the calibration preamble reword and the kind line, and the cut of the PLAN-IMPACT section's STOP line (the stop-like rule is the build-only-the-untouched-part rule in the PLAN-IMPACT findings section), the opencode code-reviewer port's two-section calibration read, with Calibration Anchor and Self-Check Before Reporting no longer adopted, the Plan impact section intake in review_loop_findings.py, and the widened PLAN-IMPACT prefix in plan_format.py. Only the two cut lines were metered (see Evidence)."
---

## Change

coder-core's plan-versus-code check tells the coder to write the `acceptance_criteria:` line as its PLAN-IMPACT findings section says, and the rule to build to the code when no criterion changes moved into that section. The section's STOP line was cut; the stop-like rule is the one in the PLAN-IMPACT findings section, which builds only the part a criterion change does not touch. code-reviewer loses the `blocker` sentence, has a Plan impact section between Ask and Nit, and its preamble points at reviewer-calibration's Disposition and Verify the Premise Before Flagging sections. reviewer-calibration names code-reviewer as a reader of those two sections and holds the optional `kind: reword|cut|narrow` line. The opencode code-reviewer port has the same Plan impact section and reads only Verify the Premise Before Flagging and Disposition; Calibration Anchor and Self-Check Before Reporting are no longer adopted there.

## Evidence

Rule-meter arms ran on code-reviewer's pre-edit text (a detached worktree of HEAD as `toolkit_root`), opus, one run per cell at the supportive, neutral and competing levels, so three runs per arm. Both scenarios are marked retired in `rule_meter_scenarios.json` after `rule_trials.py build`, because their text is cut.

- PI01 (plan-impact line, the Ask-section `[Never auto-fixed. ...]` line cut from Ask): the strict detector (`pi_line_reported`) needs a finding that opens with `PLAN-IMPACT:` and graded 0 of 3 with the line and 0 of 3 without. All three on-arm reports carried `PLAN-IMPACT:` in an Ask line after the `file:line` and none opened with it; none of the three off-arm reports carried the prefix anywhere. The prefix detector (`pi_prefix_present`: `PLAN-IMPACT:` anywhere in the report) re-graded the same six runs, with no live rerun: 3 of 3 with the line and 0 of 3 without.
- BL01 (`blocker` sentence cut): 3 of 3 with the sentence and 3 of 3 without. The planted minor defect was a plain `fix` in every run.

A rerun of either scenario is not possible from this repo after the cut; the scenarios read the pre-edit text, which master no longer holds once this merges.

## Result

The criteria rule is stated once per side and code-reviewer reads the calibration file once.

- PI01, strict reading (line opens with `PLAN-IMPACT:`): 0 of 3 with the line against 0 of 3 without.
- PI01, prefix reading (`PLAN-IMPACT:` present): 3 of 3 with the line against 0 of 3 without.
- BL01: 3 of 3 with the sentence against 3 of 3 without. ALREADY: the sentence is cut and the verdict is logged in `rule_trials.jsonl`.

The review loop now takes a line under the `### Plan impact` heading in as an ask, so the section the reviewer writes is read like the Ask section was. A `PLAN-IMPACT:` prefix wrapped in backticks or bold, on its own or after a class tag or file:line, now counts as a plan impact.

## Watch

None.

## Back-out

Revert the commit.
