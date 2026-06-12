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

0. **Check for prior triage**: If the current conversation already contains a "PR Comments Triage" table with "Valid (Actionable)" findings from an earlier `/pr-comments` run, skip steps 1-3 and reuse those findings. Go directly to step 4.

1. **Fetch + dedup via the bundled script**:

   ```bash
   bash "${CLAUDE_SKILL_DIR}/fetch-pr-comments"
   ```

   Outputs `{pr, url, inline, reviews}` JSON. Inline comments are already deduplicated — replies dropped, only the most recent comment per `(path, line, author)` kept (bots like Copilot and the Claude review bot re-review on every push) — and top-level review bodies are filtered to non-empty. If the script exits non-zero with "no PR", tell the user and stop. Do NOT re-fetch or re-dedup by hand.

2. **Triage each comment** by reading the file at the referenced path and line:
   - **Already fixed** — the code no longer matches what the comment flagged (likely addressed in a later commit)
   - **Valid** — the issue still exists in the current code
   - **Invalid / Wrong** — the commenter misunderstood the code, API, or convention
   - **Low priority** — technically valid but not worth fixing now (cosmetic, stylistic, or pre-existing)

3. **Present findings** as a table, with an Author column so the user can weight bot vs human input:

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

4. **If `+fix` modifier is present** and there are valid actionable items:
   - Format the valid findings as review feedback (file paths, line numbers, issue descriptions, author for context)
   - Invoke `/fix` skill, passing through any `+fast` or `+deep` modifier
   - If no valid items found, tell the user there's nothing to fix

5. **If `+fix` is NOT present**, end with:
   > Run `/pr-comments +fix` to auto-fix the valid items, or `/fix` manually after reviewing.

## Arguments

$ARGUMENTS
