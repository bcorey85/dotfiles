# Phase 2: Goal-blind research (before any design thinking)

5. **Dispatch `goal-blind-researcher`** (pinned — omit `model`) with the path to
   `00-ticket.md` and the task directory. It runs the whole phase and returns
   paths: questions, leak check, `02-research.md`.

   **Pass the ticket by path, never inline**, and do not repeat what the feature
   is — the agent's value is that it never learns the goal, so the repair of a
   leaked question happens outside your context. Do not hand-edit `01-questions.md`.

   Returns `UNRESOLVED after 2 cycles` → a question is entangled with the goal.
   Put it to the user and re-dispatch; do not wave it through.

6. **Walk the user through `02-research.md`, one section at a time, in the
   document's own order — never a goal-curated selection.** Present a section,
   then stop and wait; do not bundle the next section into the same turn. Answer
   questions from the document. Log whatever the exchange settles (corrected
   premise, constraint, ruled-out direction, spawned decision point): create
   `03-decisions.md` now if needed; Phase 5 appends to it. Propose nothing yet.
