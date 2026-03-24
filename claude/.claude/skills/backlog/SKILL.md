---
name: backlog
description: Capture an idea from the current conversation into docs/backlog/ for later conversion into an /eng-spec. Use when the user says "backlog", "save this idea", "dump this to backlog", "let's capture this", or "/backlog". Distills conversation context into a structured idea document.
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash]
---

# Idea

Distill the current conversation into a structured idea document at `docs/backlog/`. These are lightweight design notes — not specs. They capture _what_ and _why_ so a future `/eng-spec` run has enough context to produce a full plan.

## Modifiers

- `+name:<slug>` — Override the auto-generated filename (e.g. `+name:dark-mode-v2`).
- `wishlist` — Save to `docs/backlog/wishlist/` instead of `docs/backlog/`. Use for long-term ideas that aren't actionable in the current sprint (e.g. future framework ports, speculative features).

## Instructions

1. **Identify the idea** — Review the recent conversation to extract the core idea or feature being discussed. If the user provided a topic as an argument, use that as the focus. If unclear, ask.

2. **Check for existing ideas** — Glob `docs/backlog/*.md` and `docs/backlog/wishlist/*.md` and check if a related document already exists. If so, update it rather than creating a duplicate.

3. **Synthesize the conversation** into the following structure:

   ```markdown
   # <Title>

   > <One-line summary of the idea>

   ## Context

   Why this came up — the problem, pain point, or opportunity that sparked the idea.

   ## Proposal

   What we discussed — the approach, key decisions, and any constraints identified.
   Use bullet points. Include specific technical details from the conversation
   (component names, token values, API shapes, etc.) — these are easy to lose.

   ## Open questions

   Unresolved decisions, trade-offs, or things that need more research.
   Omit this section if there are none.

   ## References

   Links to related files, docs, tickets, or external resources mentioned in the conversation.
   Omit this section if there are none.
   ```

4. **Keep it concise** — An idea doc should be 30-80 lines. It's a capture, not a spec. Don't pad it with boilerplate or restate things that are obvious from the title.

5. **Write the file** — Save to `docs/backlog/<slug>.md` (or `docs/backlog/wishlist/<slug>.md` if the `wishlist` modifier is set). Generate a kebab-case slug from the title unless overridden with `+name:`. Check for filename collisions.

6. **Show the user** the final file path and a one-line summary of what was captured.

## Arguments

$ARGUMENTS
