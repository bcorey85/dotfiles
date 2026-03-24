---
name: merge-worktree
description: Safely merge a worktree branch into the current branch — checks for reverts, validates diff, merges.
allowed-tools: [Bash]
user-invocable: true
---

# Merge Worktree

Safely merge a `worktree-*` branch into the current branch. Validates the diff before merging to catch reverts and stale branches.

## Usage

`/merge-worktree <name>` — merges `worktree-<name>` into the current branch.

## Instructions

Execute all steps in one pass — do NOT pause for approval.

1. **Resolve branch name**: If the argument doesn't start with `worktree-`, prepend it. The branch is `worktree-<name>`.

2. **Verify branch exists**:
   ```bash
   git rev-parse --verify worktree-<name> 2>/dev/null
   ```
   If not found, list available worktree branches (`git branch | grep worktree-`) and stop.

3. **Check for new commits**:
   ```bash
   git log --oneline <current-branch>..worktree-<name>
   ```
   If empty, report "No new commits on worktree-<name> — nothing to merge." and stop.

4. **Check diff size and scope**:
   ```bash
   git diff <current-branch>..worktree-<name> --stat | tail -5
   ```

5. **Check for reverts** — look for deletions of files that exist on the current branch:
   ```bash
   git diff <current-branch>..worktree-<name> --name-only | grep -v "scripts/codemods\|docs/"
   ```
   If the diff shows deletions of component files, changeset files, or other work from the current branch, WARN the user: "This merge would revert work on the current branch. The worktree likely needs to rebase first." and STOP.

   Quick revert check — count net deletions vs additions:
   ```bash
   git diff <current-branch>..worktree-<name> --stat | tail -1
   ```
   If deletions significantly outnumber insertions, warn about potential reverts.

6. **Merge**:
   ```bash
   git merge worktree-<name> --no-edit
   ```

7. **Report**: Show the merge result — commit count, files changed, any conflicts.

## Arguments

$ARGUMENTS
