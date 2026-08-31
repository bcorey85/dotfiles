# Phase 2: Goal-blind research (before any design thinking)

5. **Dispatch `goal-blind-researcher`** (pinned — omit `model`) with the path to
   `00-ticket.md` and the task directory. It runs the phase and returns paths:
   questions, leak check, `02-research.md`.

   **Pass the ticket by path, never inline**, and don't repeat what the feature
   is — the agent's value is never learning the goal, so a leaked question's
   repair happens outside your context. Don't hand-edit `01-questions.md`.

   Returns `UNRESOLVED after 2 cycles` → a question is entangled with the goal.
   Put it to the user and re-dispatch; don't wave it through.

6. **Walk the user through `02-research.md` one section at a time, in the doc's
   own order — never a goal-curated selection.** Present one, stop, wait. Log
   whatever the exchange settles (corrected premise, constraint, ruled-out
   direction, spawned decision): create `03-decisions.md` if needed; Phase 5
   appends. Propose nothing yet.

   **Translate, don't transcribe.** Say plainly what each section _means_ in
   everyday terms and why it matters to this fix — never a bare `file.py:func`/
   line-number dump as the presentation. Those belong in the doc, not in what you
   say to the user.
