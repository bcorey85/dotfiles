---
type: "Change"
title: "review-scope stops when no base is found and the branch has commits of its own"
description: "review-scope exits 3 with a clear message instead of printing a working-tree-only scope when no base ref exists and the branch holds commits no other ref has."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-26T17:02:50-05:00"}
seq: 62
kind: "fix"
components: ["skill/review"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_scope.py::ReviewScopeNoBaseTest::test_stops_when_no_base_is_found_and_branch_has_commits_no_other_ref_has"
asked: ""
proof: []
unmeasured: ""
---

## Change

branch-base finds no base when the branch has no upstream and the repo has no origin/HEAD, origin/main, origin/master, main or master (for example a default branch named trunk or develop with no remote). review-scope then left MERGE_BASE empty, printed one stderr line, and built the scope against HEAD, which is the working tree only. Committed branch changes dropped out of the review without a stop.

Now, with no merge base, no `base=` argument and at least one other ref, review-scope exits 3 when the branch holds commits no other ref has. The message names the fix: rerun with `base=<ref>` or `merge_base=<ref>`. A lone default branch with no other ref, a branch with no commits of its own, and any run with `base=` behave as before.

## Evidence

Reproduced in a temp repo: default branch trunk, feature branch with one commit, no remote. Before the change the scope printed empty FILES and exit 0.

## Result

Test fails before and passes after. review-scope-check passes except two cases that need a free ledger cache.

## Watch

None. No intake number reads this; a stop prints its reason on stderr.

## Back-out

Revert the block that starts at "No base ref and no base= argument" in review-scope.
