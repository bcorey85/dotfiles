---
name: backlog
description: Capture an idea from the current conversation into docs/backlog/ for later conversion into an /eng-spec. Use when the user says "backlog", "save this idea", "dump this to backlog", "let's capture this", or "/backlog". Distills conversation context into a structured idea document.
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash]
---

# Idea

Distill the conversation into a lightweight idea doc at `docs/backlog/` — _what_ plus _why_ for a future `/eng-spec` run. Not a spec.

## Modifiers

- `--name <slug>` — Override the auto-generated filename (e.g. `--name dark-mode-v2`).
- `+wishlist` — save under `wishlist/` for non-sprint long-term ideas.

(Convention: `+toggle` for boolean switches, `--key value` for parameterized flags.)

## Instructions

1. **Identify the idea** from the conversation (argument topic if given); unclear means ask.

2. **Check for existing ideas** (glob both dirs) — update, never duplicate.

3. **Synthesize the conversation** into the following structure:

   ```markdown
   # <Title>

   > <One-line summary of the idea>

   ## Context

   Why this came up — the problem, pain point, or opportunity that sparked the idea.

   ## Proposal

   What we discussed — the approach, key decisions, and any constraints identified.
   Use bullet points. Include specific technical details from the conversation
   (component names, token values, API shapes, etc.).

   ## Open questions

   Unresolved decisions, trade-offs, or things that need more research.
   Omit this section if there are none.

   ## References

   Links to related files, docs, tickets, or external resources mentioned in the conversation.
   Omit this section if there are none.
   ```

4. **Keep it 30-80 lines** — capture, not spec. No boilerplate.

5. **Write the file** — `docs/backlog/<slug>.md` (kebab-case title unless `--name`; check collisions).

6. **Show the user** the final file path and a one-line summary of what was captured.

## Arguments

$ARGUMENTS
