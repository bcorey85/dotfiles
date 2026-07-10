---
name: vault-ask
disable-model-invocation: true
description: Answer a question from the vault's own notes — when something was decided, what a roadblock's history is, what the notes say about a person, project, or topic. Searches and reads the vault, answers with dates and note links as evidence. Triggers on "/vault-ask", "when did we decide", "what do my notes say about", "did I capture anything about", "search my notes".
allowed-tools: [Read, Glob, Grep, Bash]
---

# Vault Ask — answer from the notes, with receipts

Answer the user's question using ONLY the vault's contents (root: `$VAULT_DIR` if
set, else `~/vault`). This is the incident-time / "when did we decide X" recency
index, queryable. Read-only — never edit or create anything.

## Method

1. **Expand the question into search terms**: the literal phrase, plus synonyms,
   people/team/system names, and obvious misspellings (captures are typed fast —
   "arvo" for Avro). 2–4 `rg -i -l` passes over `*.md` and `*.org`, excluding
   `.git/` and `Templates/`.
2. **Establish the timeline**: `Daily/`, `Weekly/`, `Inbox/`, and `Orientations/`
   filenames carry dates — sort hits chronologically before reading.
3. **Read the hits** — the surrounding section, not just the matching line.
   Distinguish source quality: a Decisions entry in a daily note outranks a raw
   inbox capture; a Permanent note outranks both.
4. **Answer**:
   - Direct answer first, one or two sentences, with the date(s).
   - Then evidence: `date — quote or tight paraphrase — [[note name]]` (or path),
     chronological. If the position *changed* over time, show the progression —
     that's usually what the user actually needs.
   - Related-but-not-asked findings: one line at most, only if genuinely adjacent.
5. **When the vault is silent, say so plainly** — "nothing captured about X" —
   and name the nearest terms that DO appear, so the user can re-ask. Never pad
   an empty result with general knowledge: if the answer isn't from a note, it
   isn't an answer here. General knowledge is allowed only to interpret what a
   note means, never to substitute for one.

## Boundaries

- Read-only, vault-only. No writes, no code repos, no web.
- Answers cite notes or say "not captured" — there is no third option.
