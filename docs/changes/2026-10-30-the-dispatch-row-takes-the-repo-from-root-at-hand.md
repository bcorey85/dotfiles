---
type: "Change"
change_type: "fixed"
title: "the dispatch row takes the repo from ROOT= at hand-back"
description: "When a review loop's review-scope prints a ROOT= in another repo than the one its dispatch row named, the hand-back hook re-records the dispatch's repo from ROOT=, so the commit gate and the run rows credit the same repo."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T07:38:01-05:00"}
seq: 314
kind: "fix"
components: ["script/handback", "script/handback-store"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::OneCheckedHandBackTest::test_a_root_line_in_another_repo_than_the_dispatch_names_one_repo_for_the_gate"
asked: ""
proof: []
unmeasured: "No intake row counts dispatches whose ROOT= named another repo than the dispatch row."
---

## Change

The hand-back hook reads the loop's transcript, and when review-scope printed a ROOT= line there, `handback.rerecord_dispatch_repo` writes a `dispatch-repo` row (`handback_store.DISPATCH_REPO_KIND`) with the repo `loop_transcript.reviewed_repo` gives for that ROOT=. `handback_store.latest` puts that repo on the latest dispatch row. The commit gate reads the dispatch row's repo through `latest`, so it now credits the repo the run rows name. The row is written before the transcript gates run, so a hand-back that those gates deny keeps it.

## Evidence

The one-rule change (`2026-10-30-one-rule-picks-the-reviewed-repo-for-the-hand-back.md`) left this gap open: the dispatch row is written before review-scope prints ROOT=. With no `repo:` line and a ROOT= in another repo than cwd, the commit gate credited the cwd repo while the run rows named the ROOT= repo.

## Result

The test dispatches a loop from one repo with no `repo:` line, hands back a transcript whose review-scope printed a ROOT= in a second repo, and checks that the dispatch row and the commit gate's credit name the second repo, and not the first. It fails against the previous `handback.py`: the dispatch row kept the cwd repo.

## Watch

None: no intake number reads which repo a dispatch row names.

## Back-out

Remove `rerecord_dispatch_repo` and its call in `transcript_gate_reason` from `handback.py`, `DISPATCH_REPO_KIND` and its branch in `latest` from `handback_store.py`, the three tests that use the `review_scope_run` helper (`test_a_root_line_in_another_repo_than_the_dispatch_names_one_repo_for_the_gate`, `test_a_root_line_outside_any_work_tree_names_no_repo_for_the_gate`, `test_a_second_dispatch_with_a_repo_line_replaces_the_root_line_repo_for_the_gate`) with the helper, and the docstring edit in `review_commit_gate.py`.
