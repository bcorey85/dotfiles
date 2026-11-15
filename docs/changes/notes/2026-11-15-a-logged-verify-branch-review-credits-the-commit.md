---
type: "Change"
change_type: "fixed"
title: "a logged verify-branch review credits the commit of that exact tree"
description: "The review commit gate passes a commit of the tree a /verify-branch Step 1 review was logged on with verify-log review, with no ask open, so the Step 1 coder's fixes commit without a second full /review."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-15T09:33:55-06:00"}
seq: 2
kind: "fix"
components: ["script/review-commit-gate", "script/verify-common", "script/verify-log", "script/verify-prep"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_commit_of_the_tree_a_logged_branch_review_covered_passes"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/verify_common.py` gains `branch_review_covers(repo_dir)`: covers when the saved verify context for this checkout
and branch has `top` equal to this checkout, `reviewLoggedTree` equal to the tree's fingerprint now, and no open
`reviewAsks` (an ask counts as ruled when a verify-log `--asks-ruled` run that prints CLEAN saved
`reviewAsksRuledTree` equal to the logged tree; a new review log clears it). It fails closed and returns an unreadable-record problem to the caller.
`context_fingerprint` (over `tree_fingerprint`) is the one hash both verify-log and the gate use. verify-prep
carries `reviewAsksRuledTree` forward when it rebuilds the context. The three context keys are named constants in
`verify_common` (`REVIEW_LOGGED_TREE`, `REVIEW_ASKS`, `REVIEW_ASKS_RULED_TREE`), and verify-log, verify-prep and the
tests read them from there.
`review/review_commit_gate.py` `earns_credit` calls it after `is_reviewed` and prints the problem under its own
name. The `reviewed_tree` record keeps its one writer. `claude/.claude/scripts/CLAUDE.md` gains one
Owners line naming `branch_review_covers`, and its commit-credit line now reads "Converged-review commit credit". The
user approved each line directly in agent-evals-5e on 2026-11-15, relayed by agent-evals-5e, which made both edits.
The user also approved the Owners line's wording "from the saved verify context (`verify-log review` and `verify-log
--asks-ruled`)" directly on 2026-11-15, relayed by agent-evals-5e.

Why this path rather than sending Step 1's fixes through the /review loop: the diff is scripts, tests and
one Owners line in `claude/.claude/scripts/CLAUDE.md`, with no skill text. No rule-meter run: the user approved that
Owners line's wording directly. It lets no later edit commit, because the credit holds only while
the tree equals the logged one. Any edit, deletion or new file after the log voids it, except inside the task dir, or
the plan file in flat mode (nothing for a ticket-only run), that verify-prep leaves out.

Two trades, ruled accepted by the orchestrating session agent-evals-5e on 2026-11-15:
- A Step 1 coder's fixes commit without a second review. verify-prep already counts the Step 1 review plus one fix
  pass as the branch review, and the gate now agrees with it.
- A session that logs a review it never ran gets credit. Anything that runs `verify-log review`, a subagent included,
  writes the record. verify-prep already trusts this same record, and stopping forgery is out of scope for this gate.

## Evidence

judgment: on a dotfiles lane, the gate refused the commit of a logged Step 1 review's fixes. The /review it demanded
took about 28 minutes, fixed 7 more findings and ended on an unreviewed fix.

## Result

`test_review_commit_gate.py` gains 23 tests and `test_verify_branch_script.py` gains 3.
The allowed-commit tests (including an ask ruled on the logged tree and an edit inside the excluded task dir) fail on
the old gate. The denial tests (an edit after the log, an open ask, an ask ruled on another tree, another checkout or
branch) guard the new credit. The full suite passed.

## Watch

None: a fixed rule over one saved record.

## Back-out

Revert the commit.
