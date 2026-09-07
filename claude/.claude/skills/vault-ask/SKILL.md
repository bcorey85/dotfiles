---
name: vault-ask
description: Answer a question from the vault's own notes — when something was decided, what a roadblock's history is, what the notes say about a person, project, or topic. Searches and reads the vault, answers with dates and note links as evidence. Triggers on "/vault-ask", "when did we decide", "what do my notes say about", "did I capture anything about", "search my notes".
allowed-tools: [Read, Glob, Grep, Bash]
---

# Vault Ask — answer from the notes, with receipts

Answer the user's question using ONLY the vault's contents (root: `$VAULT_DIR` if
set, else `~/vault`). Read-only — never edit or create anything.

## Method

1. **Expand to search terms** (literal + synonyms + names + likely misspellings). 2–4 `rg -i -l` passes over `*.md`/`*.org`, excluding `.git/`, `Templates/`.
2. **Establish the timeline**: `daily/`/`Weekly/`/`Orientations/` filenames carry dates — sort chronologically. Org files do NOT (flat, append-only): date from the headline `[YYYY-MM-DD Day]` / `CLOSED:`, never the file.
3. **Read surrounding sections**, not just matching lines. Source quality: `cache/` notes outrank; daily Decisions outrank `notes/`. **Trust lives in the line, not the folder** — `[unverified]` = claim anywhere; unmarked `notes/` = presumed verified. **Org is the live todo state** (`TODO`/`NEXT`/`WAITING` open, `DONE`/`CANCELLED` closed + date) — daily `Open todos` and pre-org checkboxes are stale snapshots, never live evidence. Always report todo state.
4. **Answer**: direct first (1–2 sentences + dates), then chronological evidence (`date — quote/paraphrase — [[note]]`; show progression when positions changed). Related-but-unasked: one line max, only if adjacent.
5. **Vault silent → say so** ("nothing captured about X") + nearest terms for re-asking. Never pad with general knowledge — it interprets notes, never substitutes.

## Boundaries

- Read-only, vault-only. No writes, no code repos, no web.
- Answers cite notes or say "not captured" — there is no third option.
