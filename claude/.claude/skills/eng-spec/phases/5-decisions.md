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

    <!-- Anything the conversation established that is NOT a decision: a
    constraint the user named, a direction ruled out, a premise of the ticket
    they corrected. These are the first casualties of compaction and nothing
    else captures them. -->
    ```

    Items are ADD-ONLY: a decision that surfaces mid-conversation gets appended to
    the queue, never handled off-ledger.

## Then resolve

12. **Present understanding FIRST**, before any decisions: current state, the
    patterns found (ask the user to confirm they are the RIGHT ones to follow),
    constraints, and the architect's **counter-primed approaches** — three, or
    however many it said it could name. A wrong
    pattern caught here does not propagate into every downstream decision.
    Whatever this exchange settles goes under `## Direction & Constraints` in the
    ledger _as it lands_, not later.

13. **Write the answer down before you ask the next question.** The moment a
    decision resolves, `Edit` `03-decisions.md`: append the full four-field block
    (`~/.claude/skills/_shared/design-decision-format.md`) under `## Resolved`,
    tick its queue line, bump the `Status:` count. Not a note-to-self, not a
    one-liner — the finished block: Phase 6 architects and the saved spec read
    this file.

    Compacted, or unsure what is settled → re-read `02-research.md` and
    `03-decisions.md`. **Never reconstruct a resolved decision from memory, and
    never re-ask one that is already ticked.**

14. **Resolve decision points ONE AT A TIME, in prose. Never `AskUserQuestion`
    here.** A modal with a recommendation pre-selected invites a click, not a
    conversation — and the questions the user asks back, carrying constraints
    that live only in their head, never get asked. The decision points ARE the
    interview. Walk the ledger's queue, each as written English:

    - what the decision is, and why it is live (what in the research forces it)
    - the options with their real costs — **all of them**, and what each one makes
      worse
    - your recommendation, stated last and stated as a recommendation
    - **then stop and wait.** Do not bundle the next question into the same turn.

    Expect a question back rather than a choice — that is the system working.
    Follow it and ask follow-ups freely; there is no question quota.

    **Never resolve a decision by recommending harder. Ask, and wait for words.**

    **Split the check out of the decision.** A claim shaped like _"we know X
    because we looked at Y"_ — does this record exist? is this the same user? is
    this value unique? — is its own decision. Ask it as its own question, never as
    a subordinate clause.

    **Scope gate (blocking).** A decision that would add a migration, index,
    table, endpoint, or dependency the ticket did not imply: **stop and say so,
    with the cost.** Scope is the ticket-owner's call.

    Do NOT write the spec and do NOT dispatch finalization until every decision
    point and open question is resolved. **The completeness test is mechanical:
    every queue line in `03-decisions.md` ticked.** Not "the conversation feels
    finished" — read the ledger and check.
