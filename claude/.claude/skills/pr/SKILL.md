---
name: pr
description: Create a pull request from the current branch
allowed-tools: [Bash, Read, Glob, Grep, Skill, mcp__jira__getJiraIssue]
---

# Create Pull Request

Analyze the current branch's changes and create a pull request using `gh`.

## Modifiers

- `+draft` — Create a **draft** PR. Skips the Jira → In Review transition (work is still in progress). Use this for early PRs opened right after branching to track changes.
- `--base <branch>` — Target a specific base branch instead of `main`. Useful for sprint branches (e.g., `--base Sprint-A-2026`).

Convention: `+toggle` for boolean switches (no value), `--key value` for parameterized flags. Parse modifiers from `$ARGUMENTS` before processing. Both are optional and can be combined.

## Instructions

1. **Resolve the base branch** (checked in order):
   - If `--base <branch>` was provided in args, use that. (Note: `--base` is a parameterized flag, not a toggle.)
   - Else check for an existing PR on this branch: `gh pr view --json baseRefName -q .baseRefName 2>/dev/null`. If a PR exists, use its base.
   - Else default to `main` (or `master` if `main` doesn't exist).

2. **Gather context** by running these in parallel:
   - `git status` to check for uncommitted changes
   - `git log --oneline <base>..HEAD` to see all commits on this branch
   - `git diff <base>...HEAD --stat` to see the full scope of changes
   - `git branch --show-current` to get the branch name

3. **If there are uncommitted changes**, warn the user and ask if they want to commit first (suggest `/commit`) or proceed without them.

4. **If the branch hasn't been pushed**, push it with `git push -u origin <branch>`.

5. **Check for existing PR**: Run `gh pr view --json state,url,isDraft 2>/dev/null` to see if a PR already exists for this branch.
   - **If a non-draft PR exists**: inform the user and stop — nothing to do.
   - **If a draft PR exists AND `+draft` was NOT passed**: convert it to ready with `gh pr ready`, then proceed to step 9 (Jira transition). Skip PR creation.
   - **If no PR exists**: continue to step 6.

6. **Analyze ALL commits** on the branch (not just the latest) to understand the full scope of changes. Read key changed files if needed for context. If `+draft` is set and there are zero commits (empty branch), that's fine — the summary can say "WIP: branch created, implementation pending."

7. **Draft the PR**:
   - Title: short, under 70 characters. **If the branch name contains a Jira ticket key** (e.g., `TAS-1-repo-standup`), the PR title MUST follow the convention: `JIRAPROJECT-TICKETNUMBER: description` (e.g., `TAS-1: stand up monorepo`). Extract the key from the branch name.
   - Body: use this format:

   ```
   ## Summary
   <1-3 bullet points covering the full scope of changes>

   ## Test plan
   <Bulleted checklist of how to verify the changes>

   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   ```

8. **Create the PR** using:
   ```bash
   gh pr create --title "title" --base "<base>" [--draft] --body "$(cat <<'EOF'
   body here
   EOF
   )"
   ```
   Add `--draft` flag to the `gh` command if `+draft` was passed. Always pass `--base` explicitly.

9. **Return the PR URL** to the user.

10. **Move Jira ticket** (non-draft only): If `+draft` was NOT passed and the branch contains a Jira ticket key, automatically invoke the `/move-ticket in review` skill via the Skill tool after the PR is created. No confirmation needed — creating a PR implies the ticket is ready for review. Do NOT inline the Jira transition logic — always delegate to the `/move-ticket` skill.

   **If `+draft` was passed**: skip the Jira transition entirely. The ticket stays in its current status.

## Arguments

$ARGUMENTS
