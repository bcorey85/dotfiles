---
name: rebase-worktree
description: Rebase the current worktree branch onto the parent branch. Run this FROM the worktree session before the lead session merges.
allowed-tools: [Bash]
user-invocable: true
---

# Rebase Worktree

Rebase the current worktree branch onto the parent branch so the lead session can merge cleanly. This skill is meant to be run FROM a worktree Claude session.

## Usage

`/rebase-worktree` — auto-detects the parent branch and rebases onto it.
`/rebase-worktree <branch>` — rebase onto a specific branch.

## Instructions

Execute all steps in one pass — do NOT pause for approval.

1. **Verify we're on a worktree branch**:
   ```bash
   git branch --show-current
   ```
   If the branch doesn't start with `worktree-`, warn: "Not on a worktree branch. Are you sure?" but proceed if the user passed a target.

2. **Determine target branch**: If an argument was provided, use it. Otherwise, auto-detect by finding the branch this worktree was created from:
   ```bash
   git log --oneline --first-parent -20 | tail -1
   ```
   Or check `git worktree list` to find the main worktree's branch. The target is usually the branch the `cw` command was run from.

   Common targets: `chr-*`, `feature/*`, `fix/*`, `master`.

3. **Fetch latest**:
   ```bash
   git fetch origin
   ```

4. **Check if rebase is needed**:
   ```bash
   git log --oneline <target>..<current> | wc -l
   git log --oneline <current>..<target> | wc -l
   ```
   If the current branch has zero commits ahead of target, report "Already up to date." and stop.
   If the target has zero commits ahead of current, report "No new commits on target — rebase not needed." and stop.

5. **Stash any uncommitted changes**:
   ```bash
   git stash --include-untracked
   ```
   Note if anything was stashed.

6. **Rebase**:
   ```bash
   git rebase <target>
   ```
   If conflicts occur:
   - List the conflicting files
   - Do NOT auto-resolve — tell the user: "Rebase has conflicts. Resolve them manually, then run `git rebase --continue`."
   - Stop here.

7. **Pop stash** (if anything was stashed):
   ```bash
   git stash pop
   ```

8. **Report**: Show the result — how many commits were replayed, current HEAD, and confirm the branch is ready for `/merge-worktree` from the lead session.

## Arguments

$ARGUMENTS
