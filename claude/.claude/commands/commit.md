---
description: Draft a commit message from current changes
allowed-tools: [Bash]
---

# Commit

Run `git diff` (or `git diff --cached` if there are staged changes) to review what changed. Draft a commit message using `JIRAPROJECT-TICKETNUMBER: description` if the branch has a ticket key, otherwise use conventional commits (`type(scope): description`). Present the message and wait for approval before committing.

## Arguments

$ARGUMENTS
