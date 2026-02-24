---
name: commit
description: Draft a commit message from current changes, then push
allowed-tools: [Bash]
---

# Commit

Run `git diff` (or `git diff --cached` if there are staged changes) to review what changed. Draft a commit message using `JIRAPROJECT-TICKETNUMBER: description` if the branch has a ticket key, otherwise use conventional commits (`type(scope): description`). Present the message and wait for approval before committing.

## Modifiers

- `+no-push` — Skip the push to remote after committing. By default, `/commit` pushes to the tracking remote after a successful commit.

## Instructions

1. Review changes and draft a commit message (as described above).
2. Present the message and wait for user approval.
3. Create the commit.
4. **Push to remote** (unless `+no-push` was passed): Run `git push`. If no upstream is set, use `git push -u origin <branch>`. If the push fails for any reason (auth, diverged history, network), report the error clearly — do NOT retry with `--force` or destructive flags.

## Arguments

$ARGUMENTS
