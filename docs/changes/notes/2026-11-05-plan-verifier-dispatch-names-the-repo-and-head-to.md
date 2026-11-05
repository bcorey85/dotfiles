---
type: "Change"
change_type: "fixed"
title: "Plan-verifier dispatch names the repo and HEAD to verify"
description: "verify-prep puts repo: and head: lines in the plan-verifier payload, and the verifier runs every command in that repo and stops when its HEAD differs."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-05T01:35:49-06:00"}
seq: 6
kind: "fix"
components: ["script/verify-prep", "agent/plan-verifier"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_verify_branch_script.py::PrepTest::test_task_dir_prints_review_step_then_verifier_payload"
asked: ""
proof: []
unmeasured: ""
---

## Change

verify-prep's context holds `top` and `head` (`git rev-parse HEAD`), and the payload prints `repo:` and `head:` after `scope: branch`. plan-verifier.md and its opencode port say to run every git, test and check command in `repo:`, compare its HEAD with `head:`, stop on a mismatch and name the verified HEAD. The test's `assertNotIn("head", context)` is gone; no reader uses `head` for staleness.

## Evidence

judgment: a plan-verifier ran its checks in the session's cwd, another worktree, and verdicted the wrong tree. The changed test fails on the base commit and passes after.

## Result

`test_verify_branch_script.py` 136 pass (3 skipped); lint clean; rule anchor for `## Your scope` updated.

## Watch

—

## Back-out

Remove `top` and `head` from the context and the two payload lines, restore the `assertNotIn`, and remove the rule from both plan-verifier files.
