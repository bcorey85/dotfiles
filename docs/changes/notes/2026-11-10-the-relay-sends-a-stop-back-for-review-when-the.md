---
type: "Change"
change_type: "fixed"
title: "The relay sends a stop back for review when the tree changed after the converged review"
description: "code_relay.py no longer relays a stop that waits on the user when the session's latest hand-back was clean, came after HEAD's commit, and the tree is no longer the reviewed one; it tells the main session to go on with re-review feedback, so a /code resume edit after convergence gets reviewed before the commit gate denies it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T19:18:17-06:00"}
seq: 6
kind: "fix"
components: ["skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_relay.py::ReviewedTreeRelayTest::test_a_source_edit_after_the_review_sends_the_stop_back_for_review_and_leaves_relayed_unwritten"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code/code_relay.py` `relay` reads the session's latest hand-back for the repo (`handback_store.latest_for_repo`) before relaying a stop that waits on the user. When that hand-back is clean (`handback.standing_false_clean_reason` is None), was stored after HEAD's committer time (new `script_utils.head_commit_time`), and `reviewed_tree.is_reviewed` is False, it exits 0 with a rule to run the stop's `To go on:` line with the feedback "Re-run the phase review (step 5) on the current tree: files changed after the review converged." It writes no `relayed` file and no USER TEXT markers. Notes-path edits, a later commit, no session id, no commit, a non-clean or missing hand-back, and finished stops relay as before.

## Evidence

judgment: a /code resume applied the user's rulings with a coder edit to reviewed source after the loop converged; the phase-complete stop reached the user and review-commit-gate denied the commit. The key test fails on the old code (the stop was relayed as user text) and passes after.

## Result

The loop's full check on the final tree passed: 3382 tests, 0 failed.

## Watch

—

## Back-out

Revert the reviewed-tree check in `code/code_relay.py`, `head_commit_time` in `lib/script_utils.py`, and `ReviewedTreeRelayTest`.
