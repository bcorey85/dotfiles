---
name: pr-comments
description: Fetch all review comments on the current branch's PR (humans + bots), triage them, and optionally dispatch fixes. Use for "check the PR comments", "what did reviewers say", "address the review feedback on the PR".
allowed-tools: [Bash, Read, Glob, Grep, Skill]
---

# PR Comments

Pull every review comment on the current branch's PR — inline and top-level, from any author (humans, Copilot, Claude bot, etc.) — triage each one, and present actionable findings.

## Modifiers

- `+fix` — After triage, auto-dispatch `/fix` with the valid findings to fix them.
- `+fast` — Passed through to `/fix` if `+fix` is also present.
- `+deep` — Passed through to `/fix` if `+fix` is also present.

## Instructions

0. **Check for prior triage**: If the current conversation already contains a "PR Comments Triage" table with "Valid (Actionable)" findings from an earlier `/pr-comments` run, skip steps 1-4 and reuse those findings. Go directly to step 5 — that run already logged the escapes, and logging them again double-counts the flywheel.

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

4. **Log escapes** — one line per **Valid (Actionable)** finding, before any fix runs. These are defects the gates blessed and a PR reader caught, so they are ground truth for the flywheel (`/audit review`). Nothing else in the triage logs: `Already Fixed` never escaped a gate, `Invalid / Wrong` is not a defect, and `Low Priority` is a judgment call the gates were calibrated to suppress. A comment that is a new requirement or a change of direction is not an escape either — a gate cannot miss information it never had.

   Run the ratchet first (`~/.claude/skills/_shared/escape-ratchet.md`, including its ADR addendum), batching by `class` across the actionable set, then per finding:

   ```bash
   bash ~/.claude/scripts/log-escape repo="$(basename "$(git rev-parse --show-toplevel)")" stage_found=<pr-human|pr-bot> gate_missed=<review|test-intent|eng-spec> class=<bug|smell|duplication|complexity|plan-drift|test-gap|other> severity=<high|medium|low> lane=<eng-spec|code|other> guard=<...> desc="<comment gist>" file=<path>
   ```

   `stage_found` splits by commenter: `pr-human` for a person, `pr-bot` for Copilot / the Claude review bot / any other automated reviewer — the remediation differs (a bot's lens can be wired into the loop; a human's cannot). `gate_missed=eng-spec` when the code faithfully matched a wrong plan, `test-intent` when the comment is about a test pinning current behavior, `review` otherwise. Infer `lane` from the branch's planning artifacts (eng-spec doc → `eng-spec`, direct dispatch → `code`); ask only when genuinely ambiguous. Surface the proposed guard with the triage table and apply it on approval.

5. **If `+fix` modifier is present** and there are valid actionable items:
   - Format the valid findings as review feedback (file paths, line numbers, issue descriptions, author for context)
   - Invoke `/fix` skill, passing through any `+fast` or `+deep` modifier
   - If no valid items found, tell the user there's nothing to fix

6. **If `+fix` is NOT present**, end with:
   > Run `/pr-comments +fix` to auto-fix the valid items, or `/fix` manually after reviewing.

## Arguments

$ARGUMENTS
