---
type: "Change"
title: "The unreviewed-fix section says no reviewer read the last fixes and that review-again is not advised"
description: "The hand-back's last-fix section states plainly that no reviewer read the loop's last fixes, names their files, and says a review-again ends the same way."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T09:00:00-05:00"}
seq: 184
kind: "fix"
components: ["script/handback", "script/review-fix", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_a_converged_hand_back_ending_on_a_fix_finishes_and_names_the_unreviewed_fix_files"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `handback.py` `unreviewed_fix_section`: the lines read "No reviewer read the loop's last fixes. Their files are
  among: ..." and "Review-again is not advised: it ends on an unreviewed fix the same way. Read that diff yourself."
  `review_fix.py packet` and `code_step resume` print it through the same helper.

## Evidence

- Queue item code-review-again-ends-with-the-last-fix: the old wording read as a pass, and the user ran review again,
  which ended on another unreviewed fix.
- The updated tests fail on the old wording.

## Result

- The user text says what was not reviewed and what to do instead of a re-run.

## Watch

—

## Back-out

Revert the commit.
