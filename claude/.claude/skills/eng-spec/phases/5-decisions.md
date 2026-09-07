# Phase 5: Design resolution — in prose, one at a time, logged as it lands

## Open the ledger first (mechanical — no thinking, no asking)

**Do this before the first design question leaves your mouth.**

11. **`Write` `03-decisions.md`** (append, if the walkthrough created it) into
    the task directory, from the architect briefs — every decision point and open
    question they returned, one checklist line each, in the order you intend to
    raise them:

    ```markdown
    # Design Decisions — <slug>

    > Research: ./02-research.md
    > Status: 0/N resolved

    ## Queue

    - [ ] D1. <decision point, one line> — from <architect>
    - [ ] D2. <decision point> — from <architect>
    - [ ] Q1. <open question> — from <architect>

    ## Resolved

    ## Direction & Constraints

    <!-- NOT-a-decision context: user constraints, ruled-out directions, corrected ticket premises. Compaction's first casualties, captured nowhere else. -->
    ```

    Items are ADD-ONLY: a decision that surfaces mid-conversation gets appended to
    the queue, never handled off-ledger.

## Then resolve

12. **Present understanding FIRST**: current state, patterns (confirm they're the RIGHT ones), constraints, counter-primed approaches.
    Whatever settles goes under `## Direction & Constraints` _as it lands_.

13. **Write the answer down before you ask the next question.** The moment a
    decision resolves, `Edit` `03-decisions.md`: append the full four-field block
    (format: `~/.claude/skills/_shared/design-decision-format.md`) under `## Resolved`,
    tick its queue line, bump `Status:`. The finished block — Phase 6 reads this file.

    Compacted, or unsure what is settled → re-read `02-research.md` and
    `03-decisions.md`. **Never reconstruct a resolved decision from memory, and
    never re-ask one that is already ticked.**

14. **Resolve ONE AT A TIME, in prose. Never `AskUserQuestion` here** — the decision points ARE the interview:

    - what the decision is, and why it is live (what in the research forces it)
    - the options with their real costs — **all of them**, and what each one makes
      worse
    - your recommendation, stated last
    - **then stop and wait.** Do not bundle the next question into the same turn.

    Expect a question back, not a choice; follow it freely — no question quota.

    **Split the check out of the decision.** A claim shaped like _"we know X because we looked at Y"_ is its own decision — ask it separately, never as a subordinate clause.

    **Scope gate (blocking).** A decision that would add a migration, index,
    table, endpoint, or dependency the ticket did not imply: **stop and say so,
    with the cost.** Scope is the ticket-owner's call.

    No spec, no finalization until every queue line in `03-decisions.md` is ticked — the completeness test is mechanical, not "feels finished".
