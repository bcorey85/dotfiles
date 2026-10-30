---
type: "Change"
change_type: "fixed"
title: "Review commit credit goes to the repo the review ran on"
description: "review-gate-mark clean credits the tree of the repo the stored review dispatch reviewed, never the hook's cwd; the mark fires only when review-gate-mark is the command run; and the scripted review loop re-reviews a code-class fix to a .md file."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T22:52:16-05:00"}
seq: 301
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_review_of_repo_b_from_a_session_in_repo_a_credits_b_and_not_a"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `apply_mark` in `review_commit_gate.py` records the tree of the repo in the latest stored review dispatch
  (`handback_store.latest(session)["dispatch"]["repo"]`), not the hook event's cwd. When the dispatch names no repo,
  it records nothing and says so on stderr.
- The mark fires only when a simple command's command word is `review-gate-mark` (bare name or a path ending in it)
  with clean or dirty as its first argument. `shell_command.script_call_arguments` finds it. Before, any command that
  named the script, such as `rg "review-gate-mark clean" skills/`, marked the tree clean after a clean hand-back.
- The scripted review loop skips the re-review only when every applied finding is class `docs` and every changed
  file is `.md`. Before, any fix that changed only `.md` files skipped it, so a correctness fix to an agent or skill
  file went unreviewed.

## Evidence

Read of the gate and loop code at integrate/restart-bugs e44b6452.

## Result

A /review of a sibling worktree now credits that worktree and leaves the session folder's tree uncredited. A search
naming the script marks nothing. Tests pin each case. Targeted tests pass.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit.
