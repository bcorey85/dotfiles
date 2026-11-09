# Phase 2: Goal-blind research (before any design thinking)

5. **Dispatch `goal-blind-researcher`** with the path to
   `00-ticket.md` and the task directory. When Phase 1 read the ticket from a
   file inside the repo, also pass that source ticket file's path relative to the session working directory,
   so research searches skip it. It runs the phase and returns paths:
   questions, leak check, `02-research.md`.

   **Pass the ticket by path, never inline**, and don't repeat what the feature
   is. Don't hand-edit `01-questions.md`.

   Returns `UNRESOLVED after 2 cycles` → a question is entangled with the goal.
   Put it to the user and re-dispatch; don't wave it through.

   **The user cancels while research runs** → delete only
   `<task-dir>/01-questions.md` with a plain `rm <path>` (no flags), then stop
   `goal-blind-researcher` and tell the user the directory is left for them to
   remove. Stopping it does not stop the child it waits on; that child finds its questions file gone and writes nothing.

6. **Summarize `02-research.md`, then let the user drill in.** Never step
   through every section in turn.

   **Summary, one message.** Lead with a one-sentence verdict: what the research
   says about the starting state. Then one numbered line per section, in the
   doc's own order, covering every section — never a goal-curated selection.
   Each line says what the section _means_ for this fix, plus any surprise
   against the ticket (a wrong count, a missing piece, something already
   built). End with: "Name section numbers to drill into, or say go on."
   Jump nothing yet.

   **Drill-down, per section the user names.** `nvim-jump` that section's
   anchors in one call, per `~/.claude/skills/_shared/nvim-jump.md`. Then
   explain it in plain words: what it means and why it matters to this fix.
   Never a bare `file.py:func` or line dump. Several sections named at once →
   one jump call with all their anchors, grouped by section in the order named.
   Wait after each drill-down for the next pick or "go on".

   Log whatever an exchange settles (corrected premise, constraint, ruled-out
   direction, spawned decision): create `03-decisions.md` if needed; Phase 5
   appends. Propose nothing yet. "Go on" moves to Phase 3.
