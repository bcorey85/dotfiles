# Phase 5: Design resolution — one recommendation list, drill-downs on request, logged as it lands

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
    under `## Resolved`, tick its queue line, bump `Status:`. The finished block — Phase 6 reads this file.

    Record each decision as one block headed `### N. [Topic]` with:
    - **Choice:** what was picked.
    - **Reasoning:** why it wins here.
    - **Alternatives rejected:** each with the user-visible failure mode it would cause.
    - **Trade-off accepted:** what this choice costs.

    Never batch decisions into a table. No real alternative = constraint: record it under `## Direction & Constraints`. A rejection that only narrows scope needs the user's explicit sign-off. A choice that leaves credentials or data alive past the user's removal intent: state it in security terms, and it needs the user's explicit sign-off.

    Compacted, or unsure what is settled → re-read `02-research.md` and
    `03-decisions.md`. **Never reconstruct a resolved decision from memory, and
    never re-ask one that is already ticked.**

14. **Recommend the whole queue in one message, then let the user drill in.
    Never `AskUserQuestion` here, and never walk the queue one item at a time.**

    **Before the list:** do the reading each recommendation needs, so every line
    rests on research, not a guess. An item whose area `02-research.md` does not
    cover gets researched first, or marked `needs research` with no
    recommendation.

    **Recommendation list, one message.** One numbered line per unticked queue
    item, in queue order, covering every item:

    - Each item is a short block with labelled lines, never meaning carried by
      bold alone:

      ```
      **Q7. When a person is marked gone**
      - Rec: after 2 missed runs.
      - Other options: after 1 missed run; never automatically.
      - Why: one bad read would show a current user as gone for a day.
      ```

      Every real option appears, each in a few words. Why is 1–2 sentences: the
      reason, and what the strongest other option would break.
    - Start each block's heading with an emoji for its kind, 🔷 for a decision (D) and ❓ for an open question (Q), put ➡ before `Rec:`, and put a `---` line between blocks. A ⚠ goes after the kind emoji. A drill-down section opens with the same emoji heading.
    - Prefix ⚠ on any line that needs the user's own call: the scope gate below,
      a cut or narrowing of an AC, a credential or data-retention consequence, or
      a recommendation you hold weakly. Say why in the line.
    - Never present an open question that has no recommendation as if it had
      one; mark it `needs answer from <who>`.

    End with: "Name numbers to dig into, or say approve the rest."

    **Drill-down, per item the user names:** what the decision is and why it is
    live, every option with its real cost and what it makes worse, your
    recommendation stated last. Several named at once → one message, one section
    each. Expect a question back, not a choice; follow it freely. Wait after each
    drill-down.

    **"Approve the rest"** approves every recommendation the user has not named,
    except ⚠ lines: each ⚠ line needs its own explicit yes. Log each approved item
    as its own four-field block (step 13); its Reasoning names the user, the date,
    and that the user approved the recommendation from the list.

    **Split the check out of the decision.** A claim shaped like _"we know X because we looked at Y"_ is its own queue item — its own line in the list, never a subordinate clause.

    **Scope gate (blocking).** A decision that would add a migration, index,
    table, endpoint, or dependency the ticket did not imply: mark it ⚠ with the
    cost. Scope is the ticket-owner's call, so a batch approval never covers it.

    No spec, no finalization until every queue line in `03-decisions.md` is ticked — the completeness test is mechanical, not "feels finished".
