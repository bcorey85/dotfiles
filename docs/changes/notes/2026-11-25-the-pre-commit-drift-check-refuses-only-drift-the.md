---
type: "Change"
change_type: "fixed"
title: "The pre-commit drift check refuses only drift the commit adds"
description: "The pre-commit hook runs the toolkit drift check on HEAD too and refuses a commit only for problem lines the staged tree adds; drift already at HEAD passes with a note."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-25T14:36:59-06:00"}
seq: 3
kind: "fix"
components: ["script/pre-commit"]
evidence: ["tests/scripts/test_pre_commit_hook.py"]
watches: []
test: "tests/scripts/test_pre_commit_hook.py::PreCommitHookTests::test_drift_already_at_head_does_not_refuse_a_commit_that_adds_none"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

When the staged drift run fails, `.githooks/pre-commit` runs the same check on HEAD's prose tree, exported by one shell function. It refuses only for staged problem lines that HEAD does not print, and prints only those. Drift all already at HEAD passes with a stderr note giving its count. It fails closed: with no HEAD commit, or a HEAD run that passes, every staged line counts as added. A staged line without the `toolkit_drift: ` prefix always counts as added. A failing run that prints nothing is refused.

## Evidence

The pre-commit hook tests pass, including drift at HEAD with nothing added, an added line named alone, a shrinking commit, a stray output line and no HEAD commit. It also covers a failing run that prints nothing, and a HEAD run that passes so every staged problem counts as added.

## Result

Before, drift on the agent-evals side refused every toolkit prose commit, even one that did not touch the stale entry.

## Watch

—

## Back-out

Revert the commit.
