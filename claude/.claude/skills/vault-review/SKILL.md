---
name: vault-review
disable-model-invocation: true
description: Turn captured notes into action. `today` (default) — collect open follow-ups from recent daily notes, age them, help pick today's focus, and write it into today's daily note. `week` — compile the last 7 days into a weekly reflection with recurring-roadblock ages, decision log, and promotion candidates. Triggers on "/vault-review", "what's open", "weekly review", "review my notes".
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit, AskUserQuestion, Skill]
---

# Vault Review — make captures actionable

The capture pipeline (note → Inbox → /daily-recap → Daily/) organizes; this skill
closes the loop. It prepares the review — the user makes every call. Never mark a
follow-up done, promote, or delete anything without the user choosing it.

Vault root: `$VAULT_DIR` if set, else `~/vault`. Never fabricate: report only what
the notes actually contain.

## Mode: today (default — morning pass, ~2 minutes)

1. **Collect**: glob `<vault>/Daily/*.md` for the last 7 days; extract every
   unchecked `- [ ]` line with its source date. Same item appearing across days
   (fuzzy match) is ONE item aged from first appearance.
2. **Present** a numbered table: item, age in days, source note. Oldest first.
   Flag anything ≥5 days as stale — stale means "do it, delegate it, or delete it."
3. **Ask** the user (plain reply, not one question per item): which 1–3 are today's
   focus, and whether any should be closed (done/dead) or promoted.
4. **Write**: a `## Focus` section (the chosen items) at the top of
   `<vault>/Daily/<today>.md` — create the file with just that section if the
   nightly compile hasn't run yet. Mark user-closed items `- [x]` in their source
   notes.
5. **Promote on request**: "that's a ticket" → dispatch `/create-ticket` with the
   follow-up text and any context from its daily note; "worth keeping" →
   `/save-note`. Replace the vault line with a pointer (ticket key / wikilink).

## Mode: week (reflection — run Friday, or whenever the head is full)

1. **Read** the last 7 `Daily/*.md` in full.
2. **Report**:
   - **Recurring roadblocks** with day counts ("X blocked 4 of 5 days") — the
     delegation/escalation signal, most important section, lead with it.
   - **Decisions** made this week, one line each.
   - **Follow-up flow**: opened vs closed vs still open; list every stale one.
   - **Work themes**: 2–3 lines from the My work sections.
3. **Reflect**: ask 2–3 pointed questions the data supports — "this blocked all
   week; escalate, delegate, or accept?", "these three captures are the same
   problem; name it?". Questions must cite the notes, never be generic journaling
   prompts.
4. **Write** the compiled review + the user's answers to
   `<vault>/Weekly/<year>-W<iso-week>.md`. Offer the same promotions as `today`
   (tickets via `/create-ticket`, permanent notes via `/save-note`).

## Boundaries

- Writes only under the vault; never touches a code repo.
- Suggest `vault-sync` at the end if the vault has uncommitted changes.
