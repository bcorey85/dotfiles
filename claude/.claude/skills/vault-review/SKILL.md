---
name: vault-review
description: Turn captured notes into action. `today` (default) — collect open follow-ups from recent daily notes, age them, help pick today's focus, and write it into today's daily note. `week` — compile the last 7 days into a weekly reflection with recurring-roadblock ages, decision log, and promotion candidates. Triggers on "/vault-review", "what's open", "weekly review", "review my notes".
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit, AskUserQuestion, Skill]
---

# Vault Review — make captures actionable

The capture pipeline organizes; this skill closes the loop. It prepares — the user makes every call. Never close/promote/delete without the user choice.

Vault root: `$VAULT_DIR` if set, else `~/vault`. Never fabricate: report only what
the notes actually contain.

## Sources — which file is the truth

- **Live todo state**: `<vault>/org/inbox.org` and `<vault>/org/projects/*.org`.
  Open = `TODO`/`NEXT`/`WAITING` headlines. Closed = `DONE`/`CANCELLED`. Age from
  the inline capture date (`[YYYY-MM-DD Day]` under the headline), not from any
  note's filename.
  **Those two files only — an allowlist.** Everything else in `org/` is never swept:
  `books.org` (reading queue — never age/offer/flag), `bookmarks`/`questions`/`notes` (capture lanes), `journal.org` (log, below), `achievements.org` (`/weekly-recap`).
- **Journal**: `<vault>/org/journal.org` — a datetree of free-form entries.
- **`daily/*.md`**: compiled snapshots, NOT the checklist (stale `Open todos` + unticked pre-org checkboxes). **Never mine `daily/` for todos, never write todo state into it.** Read in `week` mode only (Decisions / Roadblocks / My work).

This is the one skill allowed to write todo state into org. `/daily-recap` and
`/vault-ask` treat org as read-only.

## Mode: today (default — morning pass, ~2 minutes)

1. **Collect** from org:
   - **Open todos**: every `TODO`/`NEXT`/`WAITING` headline, with its capture date.
     State-prefix anything that isn't `TODO` (e.g. `WAITING — …`).
   - **Unfiled captures**: stateless or empty-text headlines — surface separately (TODO / promote / delete decision needed).
   - **Journal loose ends**: today plus yesterday entries with intent but no matching org todo — offer as prose-inferred candidates, never invented todos.
2. **Present** numbered table (item, age, capture date), oldest first. Five days or more means stale ("do, delegate, or delete it"). Unfiled plus loose ends in short lists below.
3. **Ask** (plain reply): which 1–3 are today focus; any to close or promote.
4. **Write**:
   - `## Focus` section atop `<vault>/daily/<today>.md` (create if nightly has not run; `/daily-recap` preserves it).
   - Close chosen items **in org**: flip to `DONE`/`CANCELLED` plus `CLOSED: [<today, with time>]`, matching file format. Closing elsewhere does not close.
5. **Promote on request**: ticket goes to `/create-ticket` (todo text plus journal and daily context); keep goes to `/save-note`. Then replace headline with pointer, mark `DONE`.

## Mode: week (reflection — run Friday, or whenever the head is full)

`/weekly-recap` (cron Fridays 18:30) solely **compiles** the weekly note (Decisions/Themes/Shipped/Open todos); this mode is the **reflection** half — interrogate with the user, write back only answers. Never re-compile.

1. **Read** `<vault>/Weekly/<ISO week>.md` (`date +%G-W%V`); missing means dispatch `/weekly-recap` to compile first. One compiler, always.
2. **Deepen** with journal entries in-window plus org todo flow (opened = capture date in window; closed = `CLOSED:` in window). Lead with **recurring roadblocks** (2+ days = delegate/escalate signal).
3. **Reflect**: 2–3 pointed, note-cited questions (never generic prompts) with evidence presented first.
4. **Write** Q+A to a top `## Reflection` section (`/weekly-recap` preserves it). Touch nothing else. Same promotions as `today`.

## Boundaries

- Vault-only writes, never code repos. Todo state goes to org only; never tick `daily/` checkboxes.
- Suggest `vault-sync` on uncommitted changes.
