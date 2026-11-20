---
type: "Change"
change_type: "fixed"
title: "a standing reword ruling settles criterion rewords in drift check and plan-impact routing"
description: "A standing ruling recorded in the plan's Plan Deviations (quoted, dated) now settles each criterion reword it covers in the drift check and in the review's plan-impact routing; a cut, or a reword with no such ruling, still stops for the user."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T17:09:12-06:00"}
seq: 5
kind: "fix"
components: ["script/plan-format", "script/review-fix", "script/review-loop-script", "agent/code-reviewer", "skill/coder-core"]
evidence: ["review-loop-stops-to-ask-for-ac-sign-off-a"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_a_held_reword_impact_with_a_standing_ruling_prints_a_deviation_line_naming_it_and_no_ask"
asked: ""
proof: []
unmeasured: ""
---

## Change

The new `lib/standing_rulings.py` reads standing-ruling lines from `## Plan Deviations` and whether a PLAN-IMPACT
block is a reword (`kind: reword`, also after the reviewer's lines are joined). `plan_format.spec_ac_failures` skips the
drift row for a reword a standing ruling covers. The review's plan-impact routing adopts such a reword and prints a
deviation line naming the ruling, with no ask; it counts as applied only when the pass changed the plan or its
criteria file. The coder-core, code-reviewer and opencode PLAN-IMPACT templates carry the optional `kind:` line. The
global CLAUDE.md half of the item was cut by ruling; see the item's `## Rulings`.

## Evidence

The review fork stopped three times to ask for rewords the user's standing ruling already settled.

## Result

Standing-ruling tests in `test_plan_format.py`, `test_review_fix_script.py` and `test_review_loop_ruled.py`
(`ReviewerImpactKindTest`). A held cut and a reword with no standing ruling still ask.

## Watch

None.

## Back-out

Revert the commit.
