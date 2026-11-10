---
type: "Change"
change_type: "fixed"
title: "A fix the review loop's coder commits itself counts as a fix and is reviewed"
description: "When the review loop's fix coder commits its own fix, the loop now reads the change against the commit HEAD named before the call and reviews against the loop's start commit, so the fix counts as fixed and the next round reviews its diff instead of reporting \"the coder made no change\"."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T07:12:19-06:00"}
seq: 1
kind: "fix"
components: ["script/review-loop-script", "agent/review-loop"]
evidence: ["review-loop-misses-a-fix-the-coder-committed"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_fix_the_coder_commits_on_a_clean_tree_counts_as_fixed_and_is_reviewed"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review/review_loop_coder.py`: `coder_call` records HEAD before the call. The after snapshot and the fix diffs read the tree against that commit, so a committed fix is seen as changed and diffed against its old text, not as a whole-file deletion.
- `review/review_loop_plan.py`: new `head_commit`, reused by `changed_files_since` and `ChangeUnderReview`.
- `review/review_loop_script.py`: after any coder pass, a loop that reviews against HEAD switches its review base to the commit HEAD named when the loop started, so the committed fix and the change stay in the review scope. The coder's commit is kept.

## Evidence

Queue item: a /fix run on 2026-11-09 reported "Fixed 0, skipped 1, coder made no change" after the coder committed its fix, and the fix shipped unreviewed.

## Result

Two tests, both failing before and passing after: a committed fix on a clean tree with a `base:` line (before: `fixed` empty) and on a dirty tree with no base (before: the round fix diff read as deleting the whole file). `bash tests/run.sh` passes.

## Watch

None: the fix is pinned by tests; no intake number counts self-committed fixes.

## Back-out

Revert the commit on branch `fix/review-loop-committed-fix`.
