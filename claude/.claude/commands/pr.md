---
description: Create a pull request from the current branch
allowed-tools: [Bash, Read, Glob, Grep]
---

# Create Pull Request

Analyze the current branch's changes and create a pull request using `gh`.

## Instructions

1. **Gather context** by running these in parallel:
   - `git status` to check for uncommitted changes
   - `git log --oneline main..HEAD` (or master..HEAD) to see all commits on this branch
   - `git diff main...HEAD --stat` to see the full scope of changes
   - `git branch --show-current` to get the branch name

2. **If there are uncommitted changes**, warn the user and ask if they want to commit first (suggest `/commit`) or proceed without them.

3. **If the branch hasn't been pushed**, push it with `git push -u origin <branch>`.

4. **Analyze ALL commits** on the branch (not just the latest) to understand the full scope of changes. Read key changed files if needed for context.

5. **Draft the PR**:
   - Title: short, under 70 characters
   - Body: use this format:

   ```
   ## Summary
   <1-3 bullet points covering the full scope of changes>

   ## Test plan
   <Bulleted checklist of how to verify the changes>

   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   ```

6. **Create the PR** using:
   ```bash
   gh pr create --title "title" --body "$(cat <<'EOF'
   body here
   EOF
   )"
   ```

7. **Return the PR URL** to the user.

## Arguments

$ARGUMENTS
