---
type: "Change"
change_type: "fixed"
title: "An ask whose change starts with if accepted is not refused as conditional"
description: "`asks-done` no longer refuses an ask whose proposed change starts with \"if accepted\" as conditional; only \"if not accepted\" counts."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-15T10:08:11-06:00"}
seq: 4
kind: "fix"
components: ["script/review-asks"]
evidence: ["review-fix-coder-ignores-a-no-code-ask-ruling"]
watches: []
test: "tests/scripts/test_review_asks.py::IsConditionalChangeTest::test_a_plain_change_is_not_conditional"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review/review_asks.py` `CONDITIONAL_CHANGE`: the start-anchored `if (not )?accepted` becomes `if not accepted`. Accepting "if accepted, X" means X, so the change does not depend on a missing answer.

## Evidence

Queue item `review-fix-coder-ignores-a-no-code-ask-ruling`, part 3: asks-done refused `accepted` for the real ask change "if accepted as a cut, build `COMMIT` and `GIT_THEN_COMMIT` from `commit\b(?!-)` again ...", and the session re-sent it as `modified:` with the same text minus the condition.

## Result

The named test fails on the old script for the real shape and for "if accepted, return `[]` when the list is empty", and passes with the change. "If not accepted, keep X" stays conditional.

## Watch

None. No intake number reads this.

## Back-out

Revert the commit.

