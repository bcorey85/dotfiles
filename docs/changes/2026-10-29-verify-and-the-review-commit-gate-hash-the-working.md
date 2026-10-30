---
type: "Change"
change_type: "changed"
title: "Verify and the review commit gate hash the working tree with one function"
description: "reviewed_tree.tree_fingerprint replaces verify_common.branch_fingerprint and the commit gate's own tree hash; verify's stored fingerprints keep their exact bytes, and a reviewed-tree record from before the change counts as not reviewed until it is recorded again."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T20:09:56-05:00"}
seq: 291
kind: "fix"
components: ["skill/verify-branch", "script/review-commit-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_tree_fingerprint.py::TreeFingerprint::test_whole_tree_keeps_the_bytes_verify_stored"
asked: ""
proof: []
unmeasured: ""
---

## Change

`reviewed_tree.tree_fingerprint(top, base="HEAD", exclude_rel=None)` computes the formula verify used: "sha256:" and
the hash of `git diff --binary <base> -- .` (an optional path left out), then each untracked file's name and
`git hash-object` value. It reads git's output as raw bytes, so a non-UTF-8 name no longer breaks it.
`reviewed_tree.fingerprint` calls it against HEAD. `verify_common.branch_fingerprint` and `is_under` are deleted;
verify-prep and verify-log call the shared function and still raise VerifyError with the same messages.
`script_utils.run_or_raise` gains `as_bytes`. quality_check_cap's unrelated `tree_fingerprint` is renamed
`git_state_hash` so the two names do not collide.

## Evidence

A read-only refactor scan found the two copies.

## Result

Verify contexts and ledger review rows written before the change still match: a test pins the old function's
output on a fixed repo, checked against the old code. A commit-gate `.reviewed` record in the old bare-hex form
never matches, so the commit is denied until the next converged review records the tree again; a test pins that.
The full suite passes.

## Watch

None; a refactor with no intake number.

## Back-out

Revert the commit. Records written in the new `.reviewed` form then count as not reviewed once.
