---
type: "Change"
title: "Worktrees inside herdr open through `herdr-worktree --fork <branch>`"
description: "Worktrees inside herdr open through `herdr-worktree --fork <branch>`."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-16T00:00:00-05:00"}
seq: 5
components: ["skill/herdr"]
evidence: ["judgment"]
watches: []
---

## Change

Worktrees inside herdr open through `herdr-worktree --fork <branch>`. It opens the worktree as its own workspace, pushes the branch and forks the conversation into the new claude pane. The agent then tells the user to switch and does no more work in the old session. Outside herdr, `git worktree add` and `EnterWorktree` `path` stay

## Evidence

judgment

### Anchor reasons

Anchor `orchestration.md`, section `### Git` (evidence: removal round, judgment):

Moved from the git rules file at 79 words. Branch, commit and PR naming, focused diffs, and the worktree branch rename and push. By judgment, inside herdr the worktree line runs `herdr-worktree --fork`, which opens the worktree as its own workspace, pushes the branch and forks the conversation there. The session then does no more work. Outside herdr the old route stays. Effect unmeasured. No hook. Without it and the tools and tool-efficiency blocks, the main session named a ticket branch in lowercase and skipped the worktree rename and push. Main session only, which owns all git operations.

## Result

Effect unmeasured.

## Watch

—

## Back-out

restore the old worktree-location sentence in `orchestration.md`
