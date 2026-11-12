---
type: "Change"
change_type: "fixed"
title: "A reviewed tree split across commits keeps its commit credit"
description: "The review record now also stores the HEAD at record time, so after the first of several commits that split a reviewed tree, the commit gate still credits the later commits while that HEAD is an ancestor of the current one. An edit made after review still needs a review."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-11T23:53:09-06:00"}
seq: 15
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_reviewed_tree.py::SplitCommitCredit::test_second_commit_of_the_split_keeps_credit"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/reviewed_tree.py` `record_reviewed` writes `<session>.reviewed-base` beside the session record: repo top level ->
the HEAD at record time and the tree fingerprint. `is_reviewed`, when the current fingerprint matches no record,
fingerprints the work tree against that stored HEAD and compares it to the stored tree, only while the stored HEAD is
an ancestor of the current one. A record from a stored hand-back tree stores a base only when that tree still matches
the current HEAD; otherwise the stale base entry is dropped. `script_utils.head_commit` replaces four copies of the
HEAD lookup.

## Evidence

judgment: a session split a reviewed change into two commits; the first moved HEAD, so the second commit's
fingerprint matched no record and the gate asked for a full new review. The new `SplitCommitCredit` tests fail on the
old code.

## Result

`bash tests/run.sh` passes on the branch.

## Watch

—

## Back-out

Remove `record_base`, `matches_recorded_base` and `BASE_SUFFIX` from `lib/reviewed_tree.py`, and delete
`~/.claude/state/review-gate/*.reviewed-base`.
