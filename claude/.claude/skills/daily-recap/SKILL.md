---
name: daily-recap
disable-model-invocation: true
description: Compile today's org captures (journal entries + todo activity in the vault's org dir) and GitHub activity into a structured daily note in the Obsidian vault. Designed for a headless nightly run (launchd/systemd via install/daily-recap); also invocable manually to compile on demand.
---

# Daily Recap

Compile the day's raw material into one structured note. Idempotent per day. Org files are read-only — never modify.

Vault root: `$VAULT_DIR` if set, else `~/vault`; org dir: `<vault>/org`. Today = local `date +%F`.

## Gather (read-only; skip any unavailable source gracefully — never fail the run)

1. **Journal** (`journal.org`): every heading starting with today's date plus nested content (duplicates included). The classification source for Decisions/Roadblocks/My work.
2. **Todo activity**, **swept files** (`inbox.org` plus `projects/*.org`) only:
   - **Completed today**: `DONE` headlines with `CLOSED:` today go to My work. Ignore `CANCELLED`.
   - **Open**: every `TODO`/`NEXT`/`WAITING` headline goes to Open todos.

   **Allowlist, not all of `org/`.** Never swept: `books.org` (reading queue), `bookmarks`/`questions`/`notes` (capture lanes), `journal.org` (step-1 log), `achievements.org` (`/weekly-recap`).

3. **GitHub activity** (skip silently if `gh` is missing or unauthenticated):
   - PRs I opened or updated today: `gh search prs --author @me --updated <today>`
   - PRs I reviewed today: `gh search prs --reviewed-by @me --updated <today>`
4. Never fabricate content. A section with no source material gets `- none captured`.

## Write

Write `<vault>/daily/<today>.md`, preserving an existing `## Focus` section verbatim at top (owned by `/vault-review`; the compile owns the rest):

```markdown
# Daily Recap — <today>

## Decisions

- <one line each; who/what/why when the journal says>

## Roadblocks

- <owner and what unblocks it, when stated>

## My work

- <org items completed today, PRs opened/merged/reviewed from gh, plus work items from journal entries>

## Open todos

- <every open headline as a plain bullet, state-prefixed when not TODO (e.g. `WAITING — …`). The live checklist is the org file — this is a point-in-time record, so no checkboxes>

## Journal

<today's journal entries verbatim (entry text only — drop the org heading/timestamp scaffolding)>
```

Classify journal entries by content only when confident (unclassified still preserved under Journal). Todo state from org files only, never prose. Preserve names and ticket/PR refs exactly.

**Project tags**: leading `<word> - ` — preserve verbatim, group same-project items per section.

## Finish

Output exactly one line: the note path plus counts, e.g. `~/vault/daily/2026-07-09.md — 2 decisions, 1 roadblock, 3 completed, 6 open todos`.
