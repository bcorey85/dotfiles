---
type: "Change"
title: "Committing or pushing from a branch still carrying the auto-generated worktree prefix is refused"
description: "Committing or pushing from a branch still carrying the auto-generated worktree prefix is refused, naming the branch and asking for the rename first."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-12T00:00:00-05:00"}
seq: 5
components: ["script/git-discipline-gate"]
evidence: ["judgment"]
watches: []
---

## Change

Committing or pushing from a branch still carrying the auto-generated worktree prefix is refused, naming the branch and asking for the rename first.

## Evidence

judgment

## Result

The rename was a written instruction, skipped whenever the worktree was made in a hurry — which is exactly when it matters, because the branch then gets pushed under a machine-generated name and the remote keeps it. It shares a script and a branch lookup with the commit rules but not their exemption for repositories that allow direct commits: an unrenamed branch is wrong there too. The branch lookup itself was corrected in the same change — the previous form returns a literal placeholder and an error status on a repository with no commits, so the existing rules silently never fired there.

## Watch

—

## Back-out

—
