---
type: "Change"
change_type: "fixed"
title: "review-loop reviews the repo it was given, not the session's cwd"
description: "review-loop takes a repo: input, falls back to the first absolute path the prompt names, and runs review-scope with root= so a sibling worktree gets its own diff."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T19:11:08-05:00"}
seq: 124
kind: "fix"
components: ["agent/review-loop", "skill/review", "skill/fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_scope.py::ReviewScopeRootTest::test_review_loop_runs_review_scope_with_the_repo_as_root"
asked: ""
proof: []
unmeasured: ""
---

## Change

review-loop's Step 0 ran review-scope with no root, so a loop briefed on a sibling worktree scoped the session's own repo. The agent now takes a `repo: <path>` input. When that input is absent, it uses the repo of the first absolute path the prompt names, and only then its cwd. Step 0 passes `root=<repo>`, and when ROOT differs from the cwd, every later git, check and log command runs as `cd <ROOT> && ...`; otherwise it runs plain. `Repo root: <ROOT>` goes in each reviewer and coder prompt. /code always passes `repo:`; /review and /fix pass it when the work lives outside the session's repo. An empty `ROOT=` or an exit 2 "cannot enter" now returns a critical-blocker packet instead of falling back to git status.

The opencode port, opencode/.config/opencode/agents/review-loop.md, is knowingly not updated.

## Evidence

Judgment from three review-loop runs on 2026-10-27, each briefed with a dotfiles worktree path from a session in another repo. Each one scoped the wrong repo and recovered by hand. review-scope already had `root=`; the agent never passed it.

## Result

A test pins that Step 0's command carries `root=<repo>`. A second test shows `root=` on a worktree outside the cwd repo prints that worktree's branch and files only. A third, tests/scripts/test_code_step_review_script.py, pins that the /code review prompt carries `repo: <repo path>`.

## Watch

None: a prompt contract with a unit test.

## Back-out

Revert the commit.
