---
name: pr-comments
description: Fetch all review comments on the current branch's PR (humans + bots), triage them, and optionally dispatch fixes
allowed-tools: [Bash, Read, Glob, Grep, Skill]
---

# PR Comments

Pull every review comment on the current branch's PR — inline and top-level, from any author (humans, Copilot, Claude bot, etc.) — triage each one, and present actionable findings.

## Modifiers

- `+fix` — After triage, auto-dispatch `/fix` with the valid findings to fix them.
- `+fast` — Passed through to `/fix` if `+fix` is also present.
- `+deep` — Passed through to `/fix` if `+fix` is also present.

## Instructions

0. **Check for prior triage**: If the current conversation already contains a "PR Comments Triage" table with "Valid (Actionable)" findings from an earlier `/pr-comments` run, skip steps 1-6 and reuse those findings. Go directly to step 7.

1. **Detect the PR** for the current branch:

   ```bash
   gh pr view --json number,url --jq '{number: .number, url: .url}'
   ```

   If no PR exists, tell the user and stop.

2. **Detect the repo** (owner/name):

   ```bash
   gh repo view --json nameWithOwner --jq '.nameWithOwner'
   ```

3. **Fetch all PR review comments** (inline) using the GitHub API:

   ```bash
   gh api "repos/{owner}/{repo}/pulls/{number}/comments" --jq '[.[] | {path, line, original_line, diff_hunk, body, user: .user.login, created_at, in_reply_to_id}]'
   ```

   Also fetch top-level review bodies (skip empty ones — approvals without comments come back with an empty `body`):

   ```bash
   gh api "repos/{owner}/{repo}/pulls/{number}/reviews" --jq '[.[] | select(.body != null and .body != "") | {state, body, user: .user.login, submitted_at}]'
   ```

4. **Deduplicate**: Bots (Copilot, Claude code review, etc.) often re-review after each push. Group inline comments by `path + line + user` and keep only the most recent per `(location, author)` (by `created_at`). Drop any comment that is a reply (`in_reply_to_id != null`) — those are follow-ups, not original findings.

5. **Triage each comment** by reading the file at the referenced path and line:
   - **Already fixed** — the code no longer matches what the comment flagged (likely addressed in a later commit)
   - **Valid** — the issue still exists in the current code
   - **Invalid / Wrong** — the commenter misunderstood the code, API, or convention
   - **Low priority** — technically valid but not worth fixing now (cosmetic, stylistic, or pre-existing)

6. **Present findings** as a table, with an Author column so the user can weight bot vs human input:

   ```
   ## PR Comments Triage — PR #{number}

   ### Already Fixed
   | Author | File | Line | Issue |
   | ...    | ...  | ...  | ...   |

   ### Valid (Actionable)
   | # | Author | File | Line | Issue | Recommended Fix |
   | . | ...    | ...  | ...  | ...   | ...             |

   ### Invalid / Wrong
   | Author | File | Line | Issue | Why Invalid |
   | ...    | ...  | ...  | ...   | ...         |

   ### Low Priority
   | Author | File | Line | Issue | Reason |
   | ...    | ...  | ...  | ...   | ...    |
   ```

7. **If `+fix` modifier is present** and there are valid actionable items:
   - Format the valid findings as review feedback (file paths, line numbers, issue descriptions, author for context)
   - Invoke `/fix` skill, passing through any `+fast` or `+deep` modifier
   - If no valid items found, tell the user there's nothing to fix

8. **If `+fix` is NOT present**, end with:
   > Run `/pr-comments +fix` to auto-fix the valid items, or `/fix` manually after reviewing.

## Arguments

$ARGUMENTS
