---
name: pr-comments
description: Fetch all review comments on the current branch's PR (humans + bots), triage them, and optionally dispatch fixes. Use for "check the PR comments", "what did reviewers say", "address the review feedback on the PR".
allowed-tools: [Bash, Read, Glob, Grep, Skill]
---

# PR Comments

Pull every review comment on the branch PR (inline plus top-level, any author), triage, present actionable findings.

## Modifiers

- `+fix` means auto-dispatch the /fix skill with valid findings after triage.
- `+fast` and `+deep` pass through to the fix skill, with `+fix` only.

## Instructions

0. **Prior triage table with Valid findings already in conversation means skip to step 5 and reuse them.**

1. **Fetch + dedup via the bundled script**:

   ```bash
   bash "${CLAUDE_SKILL_DIR}/fetch-pr-comments"
   ```

   Outputs pr, url, inline, reviews JSON, deduped to latest per file-line-author with non-empty bodies. A no-PR exit means tell the user and stop. Never re-fetch or re-dedup by hand.

2. **Triage each comment** by reading the file at the referenced path and line:
   - **Already fixed** (code moved past it)
   - **Valid** (still present)
   - **Invalid** (commenter misunderstood)
   - **Low priority** (valid but not worth it now)

3. **Present findings** as tables (Author column weights bot vs human):

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

4. **Log escapes** — one line per **Valid (Actionable)** finding, before any fix. Nothing else logs: Already Fixed never escaped, Invalid is not a defect, Low Priority is calibrated suppression, new-requirement comments are not escapes.

   Ratchet per `~/.claude/skills/_shared/escape-ratchet.md` including ADR addendum, batched by class; then per finding:

   ```bash
   bash ~/.claude/scripts/log-escape repo="$(basename "$(git rev-parse --show-toplevel)")" stage_found=<pr-human|pr-bot> gate_missed=<review|test-intent|eng-spec> class=<bug|smell|duplication|complexity|plan-drift|test-gap|other> severity=<high|medium|low> lane=<eng-spec|code|other> guard=<...> desc="<comment gist>" file=<path>
   ```

   `stage_found`: human commenter means pr-human, automated reviewer means pr-bot. `gate_missed`: faithful-to-wrong-plan means eng-spec, test-pinning-behavior means test-intent, else review. `lane` from planning artifacts; ask when ambiguous. Surface proposed guard with the table; apply on approval.

5. **If `+fix` modifier is present** and there are valid actionable items:
   - Format valid findings as review feedback (paths, lines, issues, author). Aikido findings also pass each comment's `id` from the fetch output as `comment_id` for thread replies in the fix skill.
   - Invoke the fix skill, passing through +fast or +deep; nothing valid means say so.
6. **If `+fix` is NOT present**, end with:
   > Run `/pr-comments +fix` to auto-fix the valid items, or `/fix` manually after reviewing.

## Arguments

$ARGUMENTS
