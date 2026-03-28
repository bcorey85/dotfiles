---
name: copilot-review
description: Fetch GitHub Copilot review comments from the current branch's PR, triage them, and optionally dispatch fixes
allowed-tools: [Bash, Read, Glob, Grep, Skill]
---

# Copilot Review

Pull GitHub Copilot's automated review comments from the current branch's PR, triage each one, and present actionable findings.

## Modifiers

- `+fix` — After triage, auto-dispatch `/fix-feedback` with the valid findings to fix them.
- `+fast` — Passed through to `/fix-feedback` if `+fix` is also present.
- `+deep` — Passed through to `/fix-feedback` if `+fix` is also present.

## Instructions

0. **Check for prior triage**: If the current conversation already contains a "Copilot Review Triage" table with "Valid (Actionable)" findings from an earlier `/copilot-review` run, skip steps 1-6 and reuse those findings. Go directly to step 7.

1. **Detect the PR** for the current branch:
   ```bash
   gh pr view --json number,url --jq '{number: .number, url: .url}'
   ```
   If no PR exists, tell the user and stop.

2. **Detect the repo** (owner/name):
   ```bash
   gh repo view --json nameWithOwner --jq '.nameWithOwner'
   ```

3. **Fetch Copilot review comments** using the GitHub API:
   ```bash
   gh api "repos/{owner}/{repo}/pulls/{number}/comments" --jq '[.[] | select(.user.login == "Copilot") | {path, line, original_line, diff_hunk, body, created_at, in_reply_to_id}]'
   ```
   Also fetch top-level review bodies (not inline comments):
   ```bash
   gh api "repos/{owner}/{repo}/pulls/{number}/reviews" --jq '[.[] | select(.user.login == "Copilot") | {state: .state, body: .body, submitted_at: .submitted_at}]'
   ```

4. **Deduplicate**: Copilot often re-reviews after each push. Group comments by `path + line` and keep only the most recent one per location (by `created_at`). Drop any comment that is a reply (`in_reply_to_id != null`) — those are follow-ups, not original findings.

5. **Triage each comment** by reading the file at the referenced path and line:
   - **Already fixed** — the code no longer matches what Copilot flagged (likely fixed in a later commit)
   - **Valid** — the issue still exists in the current code
   - **Invalid / Wrong** — Copilot misunderstood the code, API, or convention
   - **Low priority** — technically valid but not worth fixing now (cosmetic, stylistic, or pre-existing)

6. **Present findings** as a table:

   ```
   ## Copilot Review Triage — PR #{number}

   ### Already Fixed
   | File | Line | Issue |
   | ...  | ...  | ...   |

   ### Valid (Actionable)
   | # | File | Line | Issue | Recommended Fix |
   | . | ...  | ...  | ...   | ...             |

   ### Invalid / Wrong
   | File | Line | Issue | Why Invalid |
   | ...  | ...  | ...   | ...         |

   ### Low Priority
   | File | Line | Issue | Reason |
   | ...  | ...  | ...   | ...    |
   ```

7. **If `+fix` modifier is present** and there are valid actionable items:
   - Format the valid findings as review feedback (file paths, line numbers, issue descriptions)
   - Invoke `/fix-feedback` skill, passing through any `+fast` or `+deep` modifier
   - If no valid items found, tell the user there's nothing to fix

8. **If `+fix` is NOT present**, end with:
   > Run `/copilot-review +fix` to auto-fix the valid items, or `/fix-feedback` manually after reviewing.

## Arguments

$ARGUMENTS
