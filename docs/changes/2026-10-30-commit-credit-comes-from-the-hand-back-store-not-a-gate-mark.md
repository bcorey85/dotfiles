---
type: "Change"
change_type: "removed"
title: "commit credit comes from the hand-back store, not a gate mark"
description: "The review-gate-mark command is gone: a converged or deferred review-loop hand-back of the commit's repo credits the commit by itself."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T00:13:21-05:00"}
seq: 389
kind: "fix"
components: ["script/review-commit-gate", "script/review-fix", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewCommitGateTest::test_a_review_gate_mark_command_passes_and_changes_no_state"
asked: ""
proof: []
unmeasured: "The mark was a second path to the same credit the hand-back store already gives; no intake number counts mark calls."
---

## Change

`review-gate-mark` and the commit gate's mark handling are deleted. `/review` and `/fix` no longer tell the session to run a mark, and `review_fix.py` prints no mark line in any ACTION. A Bash command that names `review-gate-mark` now passes the gate and changes no state. A commit after coder work earns credit from a merge it concludes, a tree a clean review-loop recorded as reviewed (/code's phase finish or the loop's own hand-back), or the session's latest review-loop hand-back when it is converged or deferred, answers a dispatch of the commit's repo, and was stored after the session went dirty. A review-loop dispatch whose first absolute path lies in no work tree now records the dispatch's cwd repo, so a prompt that names a plan file outside the repo still credits the repo it ran in.

The `Bash(*review-gate-mark*)` hook entry in `claude/.claude/settings.json` stays until the user removes it, together with its row in `tests/scripts/test_hook_if_filters.py`.

## Evidence

The mark was a second, model-run step that could be skipped, run on the wrong status, or denied, while the hand-back store already held the same verdict, its repo and its time. The queue item asked that no skill, agent or ACTION line send a mark and that the store alone credit the commit.

## Result

Tests cover a mark command that changes no state, each hand-back status, another session's hand-back, a later review-loop dispatch, the latest hand-back winning, a missing dispatch row, a missing `handback.py`, and a first prompt path outside any work tree.

`test_a_converged_hand_back_after_the_coder_lets_the_commit_through_without_a_mark`, which the 2026-10-27 review-commit-gate change names, is now `test_a_coder_dispatched_after_a_converged_hand_back_revokes_its_credit`: it seeds the coder dispatch before the hand-back, so its first commit proves the credit.

`handback.py`, `review_commit_gate.py` and `staged_claim_gate.py` now find a work tree's top through one shared `script_utils.work_tree_top`, which returns the real path.

## Watch

None: no intake number reads mark calls.

## Back-out

Restore `claude/.claude/scripts/review/review-gate-mark`, `apply_mark` and the `MARK` regex in `review_commit_gate.py`, the `MARK_CLEAN`/`MARK_DIRTY`/`KEEP_DIRTY` lines and `gate_mark_line` in `review_fix.py`, the mark steps in skills/review/SKILL.md, skills/fix/SKILL.md and both review-loop.md copies, and the cwd fallback in `reviewed_repo` in `handback.py`; revert the matching tests.
