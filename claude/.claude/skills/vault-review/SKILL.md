---
name: vault-review
description: Turn captured notes into action. `today` (default) — collect open follow-ups from recent daily notes, age them, help pick today's focus, and write it into today's daily note. `week` — compile the last 7 days into a weekly reflection with recurring-roadblock ages, decision log, and promotion candidates. Triggers on "/vault-review", "what's open", "weekly review", "review my notes".
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit, AskUserQuestion, Skill]
---

# Vault Review — make captures actionable

The capture pipeline (org capture → `/daily-recap` → `Daily/`) organizes; this skill
closes the loop. It prepares the review — the user makes every call. Never mark a
todo done, promote, or delete anything without the user choosing it.

Vault root: `$VAULT_DIR` if set, else `~/vault`. Never fabricate: report only what
the notes actually contain.

## Sources — which file is the truth

- **Live todo state**: `<vault>/org/**/*.org`. Open = `TODO`/`NEXT`/`WAITING`
  headlines. Closed = `DONE`/`CANCELLED`. Age from the inline capture date
  (`[YYYY-MM-DD Day]` under the headline), not from any note's filename.
- **Journal**: `<vault>/org/journal.org` — a datetree of free-form entries.
- **`Daily/*.md`**: compiled, point-in-time records. They are NOT the checklist —
  their `Open todos` bullets are a snapshot of org as of that night, and older notes
  may carry `- [ ]` checkboxes from the pre-org system that nothing ever ticks.
  **Never mine `Daily/` for open todos and never write todo state into it.** Read it
  in `week` mode only, for its Decisions / Roadblocks / My work structure.

This is the one skill allowed to write todo state into org. `/daily-recap` and
`/vault-ask` treat org as read-only.

## Mode: today (default — morning pass, ~2 minutes)

1. **Collect** from org:
   - **Open todos**: every `TODO`/`NEXT`/`WAITING` headline, with its capture date.
     State-prefix anything that isn't `TODO` (e.g. `WAITING — …`).
   - **Unfiled captures**: headlines with NO state keyword, and headlines whose text
     is empty. `/daily-recap` collects neither, so they are invisible to the whole
     pipeline and rot silently. Surface them separately — they need a decision:
     make it a TODO, promote it, or delete it.
   - **Loose ends in the journal**: scan today's and yesterday's journal entries for
     an intent that has no matching org todo ("only feedback is X", "need to Y").
     Offer it as a candidate, clearly marked as inferred from prose — never invent
     a todo the journal doesn't state.
2. **Present** a numbered table: item, age in days, capture date. Oldest first.
   Flag anything ≥5 days as stale — stale means "do it, delegate it, or delete it."
   Unfiled captures and journal loose ends go in their own short lists below it.
3. **Ask** the user (plain reply, not one question per item): which 1–3 are today's
   focus, and whether any should be closed (done/dead) or promoted.
4. **Write**:
   - A `## Focus` section (the chosen items) at the top of `<vault>/Daily/<today>.md`
     — create the file with just that section if the nightly compile hasn't run yet.
     `/daily-recap` preserves this section verbatim.
   - Close user-chosen items **in org**: flip the keyword to `DONE` (or `CANCELLED`
     if dead) and add `CLOSED: [<today, with time>]` on the following line, matching
     the file's existing format. Closing anywhere else does not close it.
5. **Promote on request**: "that's a ticket" → dispatch `/create-ticket` with the
   todo text and any context from the journal or its daily note; "worth keeping" →
   `/save-note`. Then replace the org headline's text with a pointer (ticket key /
   wikilink) and mark it `DONE`.

## Mode: week (reflection — run Friday, or whenever the head is full)

`/weekly-recap` (cron, Fridays 18:30) is the sole **compiler** of the weekly note —
it owns Decisions / Themes / Shipped / Open todos. This mode is the **reflection**
half: it reads that compile, interrogates it with the user, and writes only the
answers back. Never re-compile those sections here; the next `/weekly-recap` run
overwrites everything it owns.

1. **Read** `<vault>/Weekly/<ISO week>.md` (label: `date +%G-W%V`). If it does not
   exist yet — running mid-week, or before Friday's cron — dispatch `/weekly-recap`
   to compile it first, then read it. One compiler, always.
2. **Deepen it** with what the compile does not carry: the journal entries in that
   window (`<vault>/org/journal.org`) and the todo flow from org (opened = capture
   date in window; closed = `CLOSED:` in window). Lead the read with **recurring
   roadblocks** — a blocker appearing on 2+ days is the delegation/escalation signal.
3. **Reflect**: ask 2–3 pointed questions the data supports — "this blocked all
   week; escalate, delegate, or accept?", "these three captures are the same
   problem; name it?". Questions must cite the notes, never be generic journaling
   prompts. Present the evidence for each question, then ask.
4. **Write** the questions and the user's answers to a `## Reflection` section at the
   top of that same weekly note — `/weekly-recap` preserves it verbatim, so this
   survives the next compile. Nothing else in the file is yours to touch. Offer the
   same promotions as `today` (tickets via `/create-ticket`, notes via `/save-note`).

## Boundaries

- Writes only under the vault; never touches a code repo.
- Todo state changes go to org and nowhere else. Never tick a `- [ ]` in `Daily/`
  to mean "done" — nothing reads it.
- Suggest `vault-sync` at the end if the vault has uncommitted changes.
