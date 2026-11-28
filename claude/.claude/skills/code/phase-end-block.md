## Phase-Complete Block

**B — Stop for sign-off** (decision rules 2–6):

```
Phase <N> complete. Risk: <high | low | low — Phase 1 calibration | low — exception>. Stopped for your review.

Behavior delta (observable change + its proof, max 3 — no internals, no paths):
- <before → after, user-visible>. See it: <test name / command / UI flow>.

Check yourself (answer each in your head; open the file only for one you cannot):
- <question about this phase's code>? `<path>:<line>`

Models: <each writing agent (phase coder, review loop fix coder, asks coder) — the model it ran on, or its own default>

Plan changes adopted (no criterion changed):
- <deviation line>

Criterion changes ruled by the session (owner <session|plan>):
- <deviation line>

Plan changes awaiting sign-off (criterion changes, not applied):
- <assumed → found → what changes>

Asks decided:
- <question> — <accepted | rejected>: <reason>

Read first (/stage queue, blast-radius order):
  ESCALATE:
  - <path> — <classifier reason>
  READ / SKIM:
  - <path>
Staged mechanically (<n>) — invariant-verified, skip.

Agent-verified (evidence in the plan):
- <item — one-line evidence summary>

Human-only verification remaining:
- <item>

Next:
  1. Read the queue (the agent notes in the hunk review pane); spot-check the evidence lines; run the human-only items.
  2. Stage what you've read, then commit it. `Commit subject: <subject>`.
  3. Run /clear and /code to start Phase <N+1> fresh, or `/code resume <plan path>` to go on in this context.

Revisions to Phase <N>: `/code resume <plan path> <your feedback>`.
```

Omit either plan-change list and the asks list when it is empty.

**C — Last phase** (decision rule 1): block B's walkthrough and verification lists, with the "Next" block replaced by:

```
All phases complete. Next: read the queue, stage what you've read, then commit it. `Commit subject: <subject>`. Then read the Close pass recap's residue, run its smoke-test checklist, then you open the PR.
```

Verification items come from the just-finished phase's `#### Manual Verification:` section, split by the `agent-verified` / `human-only` tags. When that section is empty, omit both lists and replace step 1 with "Read the /stage queue."

Skill-invoke `/stage` to build the "Read first" queue and render it verbatim, in its order. The behavior delta comes from the coder's handoff (absent one, derive it from the diff and mark `derived from diff`).

Write two or three check-yourself questions from the coder's `WHY:` notes and the phase's diff. Each asks what calls a new function, what happens when a new branch fails, or what state a new write changes, and ends with the `path:line` that answers it. Never answer a question in the block.
