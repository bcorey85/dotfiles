---
name: daily-recap
description: Compile today's raw captures (vault Inbox) and GitHub activity into a structured daily note in the Obsidian vault. Designed for a headless nightly run (launchd/systemd via install/daily-recap); also invocable manually to compile on demand.
---

# Daily Recap

Compile the day's raw material into one structured note. Idempotent: re-running on the same day rewrites today's note from the same sources.

Vault root: `$VAULT_DIR` if set, else `~/vault`. Today = local `date +%F`.

## Gather (read-only; skip any unavailable source gracefully — never fail the run)

1. **Captures**: `<vault>/Inbox/<today>.md` — raw timestamped one-liners from the `note` script. Also glob `<vault>/Inbox/*.md` for older files with unprocessed captures: no `<!-- processed -->` marker at all, OR capture lines appended after the last marker (the `note` script appends blindly, so post-compile captures land below it). Include those lines flagged with their date.
2. **GitHub activity** (skip silently if `gh` is missing or unauthenticated):
   - PRs I opened or updated today: `gh search prs --author @me --updated <today>`
   - PRs I reviewed today: `gh search prs --reviewed-by @me --updated <today>`
3. Never fabricate content. A section with no source material gets `- none captured`.

## Write

Write `<vault>/Daily/<today>.md` (create the folder if needed). If the file already
exists and has a `## Focus` section (written by `/vault-review today`), preserve it
verbatim at the top — the compile owns every other section, never that one:

```markdown
# Daily Recap — <today>

## Decisions
- <one line each; who/what/why when the capture says>

## Roadblocks
- <owner and what unblocks it, when stated>

## My work
- <PRs opened/merged/reviewed from gh, plus work items from captures>

## Follow-ups
- [ ] <anything phrased as a todo, question, or "need to">

## Raw captures
<today's inbox lines verbatim>
```

Classify captures by content; when ambiguous, put the line in Follow-ups rather than dropping it. Captures beginning `done:` are explicit completions — list them under My work (prefix stripped), never under Follow-ups; the weekly compile uses them to retire carried follow-ups. Preserve people's names and ticket/PR references exactly.

**Project tags**: a leading `<word> - ` (e.g. `cube - `, `cdc - `) is a project tag. Preserve it verbatim in classified lines and group same-project items together within a section.

## Finish

- Append `<!-- processed <ISO timestamp> -->` to each inbox file that was compiled.
- Output exactly one line: the note path plus counts, e.g. `~/vault/Daily/2026-07-07.md — 3 decisions, 2 roadblocks, 5 follow-ups`.
