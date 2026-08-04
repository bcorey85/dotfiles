---
name: merge
description: Commit, rebase, and merge the current branch.
disable-model-invocation: true
allowed-tools: Read, Bash, Glob, Grep
---

<!-- Customize the commit style and rebase behavior to match your workflow. -->

**Arguments:** `$ARGUMENTS`

Check the arguments for flags:

- `--keep`, `-k` → keep the branch and its worktree after merging

Strip all flags from arguments.

Commit, rebase, and merge the current branch.

This command finishes work on the current branch by:

1. Committing any staged changes
2. Rebasing onto the base branch
3. Merging into the base branch and cleaning up

## Step 1: Commit

If there are staged changes, commit them. Use lowercase, imperative mood, no conventional commit prefixes. Skip if nothing is staged.

## Step 2: Rebase

The base branch is the local default branch — "main", or "master" when the repo
has no "main".

Rebase onto the local base branch (do NOT fetch from origin first):

```
git rebase <base-branch>
```

IMPORTANT: Do NOT run `git fetch`. Do NOT rebase onto `origin/<branch>`. Only rebase onto the local branch name (e.g., `git rebase main`, not `git rebase origin/main`).

If conflicts occur:

- BEFORE resolving any conflict, understand what changes were made to each
  conflicting file in the base branch
- For each conflicting file, run `git log -p -n 3 <base-branch> -- <file>` to
  see recent changes to that file in the base branch
- The goal is to preserve BOTH the changes from the base branch AND our branch's
  changes
- After resolving each conflict, stage the file and continue with
  `git rebase --continue`
- If a conflict is too complex or unclear, ask for guidance before proceeding

## Step 3: Merge

The rebase in step 2 makes this a fast-forward:

```
git checkout <base-branch>
git merge --ff-only <branch>
```

Then clean up, unless `--keep` was passed:

```
git worktree remove <worktree-path>   # only if the branch had its own worktree
git branch -d <branch>
```
