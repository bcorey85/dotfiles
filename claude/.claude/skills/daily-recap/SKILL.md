---
name: daily-recap
disable-model-invocation: true
description: Compile today's org captures (journal entries + todo activity in the vault's org dir) and GitHub activity into a structured daily note in the Obsidian vault. Designed for a headless nightly run (launchd/systemd via install/daily-recap); also invocable manually to compile on demand.
---

# Daily Recap

Compile the day's raw material into one structured note. Idempotent: re-running on the same day rewrites today's note from the same sources. The org files are read-only sources — never modify them.

Vault root: `$VAULT_DIR` if set, else `~/vault`; org dir: `<vault>/org`. Today = local `date +%F`.

## Gather (read-only; skip any unavailable source gracefully — never fail the run)

1. **Journal**: `<vault>/org/journal.org` — every heading (any star depth) whose title starts with today's date, plus everything nested under it. Duplicate same-day headings can exist alongside the datetree — collect them all. These free-form entries are the classification source for Decisions/Roadblocks/My work.
2. **Todo activity**: every `.org` file under `<vault>/org/` —
   - **Completed today**: `DONE` headlines whose `CLOSED:` timestamp is today → My work. Ignore `CANCELLED`.
   - **Open**: every `TODO`/`NEXT`/`WAITING` headline → Open todos.
3. **GitHub activity** (skip silently if `gh` is missing or unauthenticated):
   - PRs I opened or updated today: `gh search prs --author @me --updated <today>`
   - PRs I reviewed today: `gh search prs --reviewed-by @me --updated <today>`
4. Never fabricate content. A section with no source material gets `- none captured`.

## Write

Write `<vault>/Daily/<today>.md` (create the folder if needed). If the file already
exists and has a `## Focus` section (written by `/vault-review today`), preserve it
verbatim at the top — the compile owns every other section, never that one:

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

Classify journal entries by content, and only when confident — an unclassified entry is still preserved under Journal, so nothing is lost. Todo state comes only from the org files (DONE + CLOSED), never inferred from prose. Preserve people's names and ticket/PR references exactly.

**Project tags**: a leading `<word> - ` (e.g. `cube - `, `cdc - `) is a project tag. Preserve it verbatim in classified lines and group same-project items together within a section.

## Finish

Output exactly one line: the note path plus counts, e.g. `~/vault/Daily/2026-07-09.md — 2 decisions, 1 roadblock, 3 completed, 6 open todos`.
