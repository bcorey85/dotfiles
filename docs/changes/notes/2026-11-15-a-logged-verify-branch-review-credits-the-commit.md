---
type: "Change"
change_type: "fixed"
title: "a logged verify-branch review credits the commit of that exact tree"
description: "The review commit gate passes a commit of the tree a /verify-branch Step 1 review was logged on with verify-log review, with no ask open, so the Step 1 coder's fixes commit without a second full /review."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-15T09:33:55-06:00"}
seq: 2
kind: "fix"
components: ["script/review-commit-gate", "script/verify-common", "script/verify-log", "skill/verify-branch"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_commit_of_the_tree_a_logged_branch_review_covered_passes"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/verify_common.py` gains `branch_review_covers(repo_dir)`: True when the saved verify context for this checkout
and branch has `top` equal to this checkout, `reviewLoggedTree` equal to the tree's fingerprint now, and no open
`reviewAsks`. It fails closed. `context_fingerprint` is now the one hash both verify-log and the gate use.
`review/review_commit_gate.py` `earns_credit` calls it after `is_reviewed`. The `reviewed_tree` record keeps its one
writer.

Why this path rather than sending Step 1's fixes through the /review loop: it is a script-only diff of about 170 lines
with no skill text, so it needs no rule-meter runs. It lets no later edit commit, because the credit holds only while
the tree equals the logged one. Any edit, deletion or new file after the log voids it. The Step 1 coder's own fixes
are not re-reviewed. verify-prep already counts that review plus one fix pass as the branch review, and the gate now
agrees with it.

## Evidence

judgment: on a dotfiles lane, the gate refused the commit of a logged Step 1 review's fixes. The /review it demanded
took about 28 minutes, fixed 7 more findings and ended on an unreviewed fix.

## Result

`test_review_commit_gate.py` gains 13 tests. The allowed-commit tests fail on the old gate. The denial tests (an edit
after the log, an open ask, another checkout or branch) guard the new credit. The full suite passed (4186 tests, 0
failed).

## Watch

None: a fixed rule over one saved record. Known limits: anything that can run verify-log can log a review, a
subagent included. And an ask ruled with `--asks-ruled` leaves `reviewAsks` set, so it still owes a /review.

## Back-out

Revert the commit.
