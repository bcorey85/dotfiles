---
type: "Change"
change_type: "fixed"
title: "A plan ticked after review keeps the commit credit"
description: "A /code commit of reviewed work now passes the commit gate after a later coder ticks the plan's status line or edits another note, instead of being denied until a whole new /review (about 6 minutes) runs; any code edit after the review is still denied."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T04:10:32-06:00"}
seq: 440
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_plan_under_docs_ticked_after_the_converged_review_keeps_the_commit_credit"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The tree a review credits now leaves out the repo's notes paths: Markdown under the top-level docs/ folder and Markdown at a path the committed `.claude/notes-paths` list names, the same paths a notes-only commit ships without review.
- The notes-path rules moved from the commit gate into a new `lib/notes_paths.py`, which the gate and `lib/reviewed_tree.py` both read. `reviewed_tree.reviewed_fingerprint` is the credit form; `record_reviewed`, `is_reviewed` and the hand-back row's stored tree use it.
- Every other tree identity (verify, the quality-check cap, the full check, the capped-review status) keeps the whole-tree fingerprint. A tree with no notes path gives the same value in both forms, so records written before this change stay valid.
- A list read from HEAD with a bad entry counts as empty, so only docs/ Markdown is left out; each bad line is printed to stderr with a `[reviewed-tree]` label.

## Evidence

- A /code run's review converged and the plan impact was deferred, yet the gate denied the coder's commit three times: the tick coder's Phase Status line changed the tree fingerprint.

## Result

- The new gate tests fail before the change (3 of the pass cases) and pass after. The deny cases pass both times: a code file under docs/, a Markdown file outside docs/ and the list, a non-Markdown file under a listed folder, a folder listed only in the working tree, and a bad list.
- Full suite: 2975 tests, 0 failed, lint clean. One /review converged with 6 fixes and one accepted ask.

## Watch

None: no intake number counts gate denials of reviewed work.

## Back-out

Revert the commit. Stored reviewed records stay readable in either direction.
