---
name: commit
description: Draft a commit message from current changes, then push
allowed-tools: [Bash]
---

# Commit

Commit staged changes and push to remote. This skill is NOT complete until the push succeeds (or `+no-push` is active). Do NOT stop to ask for approval — execute the full pipeline in one pass.

The USER is responsible for staging files. Claude NEVER stages files. Draft the commit message from staged changes only (`git diff --cached`), then commit and push.

Use `JIRAPROJECT-TICKETNUMBER: description` if the branch has a ticket key, otherwise use conventional commits (`type(scope): description`).

## Modifiers

- `+no-push` — Skip the push to remote after committing. By default, `/commit` pushes to the tracking remote after a successful commit.

## Instructions

Execute all steps in a single pass — do NOT pause for user approval between steps.

1. Run `git diff --cached --stat` to see what's staged. Also run `git status --short` to check for unstaged/untracked changes.
2. **If nothing is staged**: Tell the user "Nothing staged. Stage your changes with `git add` first, then re-run `/commit`." Stop here.
3. **If there are unstaged or untracked changes** beyond what's staged: Briefly note them (e.g., "FYI: 3 unstaged files not included in this commit: [list]"). Do NOT stage them — just inform.
4. Draft a commit message from the staged diff.
5. Create the commit.
6. **Push to remote** (unless `+no-push` was passed): Run `git push`. If no upstream is set, use `git push -u origin <branch>`. If the push fails for any reason (auth, diverged history, network), report the error clearly — do NOT retry with `--force` or destructive flags.
7. **Confirm completion**: Report the commit hash, branch name, and push result. Do NOT end without confirming the push succeeded.

## Arguments

$ARGUMENTS
