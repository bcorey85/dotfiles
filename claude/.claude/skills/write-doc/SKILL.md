---
name: write-doc
description: Write a reference doc someone will actually read — short, scannable, code-pointer-anchored. Use when the user says "write a doc", "/write-doc", "/doc", "document X", or asks for an architecture/behavioral/eng-arch markdown file in a /docs folder. Do NOT use for ADRs (use /eng-spec or /push-arch), READMEs, or PR descriptions.
---

# Write-doc

Produce one markdown doc that a tired engineer can skim in 30 seconds and learn the thing. Reference docs, not essays.

## Arguments

`<topic>` — what to document. Optional: target path (e.g. `<repo>/docs/eng-arch/<name>.md`). If unspecified, infer the right location from project conventions and confirm before writing.

## Phase 1 — Scope check

Before searching or writing, answer in one line each:

- **Reader**: who picks this up cold? (Team lead. New hire. On-call. Pick one.)
- **Question it answers**: the one question the reader has when they open this file.
- **Genre**: behavioral (what the code does at runtime) / structural (how the code is laid out) / decision (why we chose X) / pointer (where things live). One genre per doc.
- **Competing docs**: name the existing doc this could overlap with, or "none".

If you can't fit reader + question + genre on one line each, the scope is too broad. Split or narrow before continuing.

## Phase 2 — Stale/dup pre-write check

Run in parallel:

1. `grep -rln "<topic-keyword>" <repo>/docs/` — does a doc on this already exist?
2. `grep -rln "<topic-keyword>" <sibling-repos>/docs/` if cross-repo facts are involved
3. Glob `**/*.md` in the target directory — what's the neighbor density?

For any hit, open it. Decide explicitly: **extend the existing doc**, **replace it**, or **write new and cross-link**. Do not silently duplicate. If extending, stop here and use Edit on the existing file.

## Phase 3 — Budget and structure

**Hard caps** (lines, including blanks and headings):

| Genre      | Cap | Rationale                                     |
| ---------- | --- | --------------------------------------------- |
| behavioral | 120 | Reader is debugging or onboarding, in a hurry |
| structural | 80  | Mostly tables and pointers                    |
| decision   | 60  | Context + decision + consequences             |
| pointer    | 40  | Index, not content                            |

If the topic genuinely needs more, **split it**. Two 100-line docs that cross-link beat one 200-line doc.

**Required structure**:

```
# <doc title — concrete, not abstract>

<One-sentence purpose. What this doc is and is not.>

## TL;DR

<3-5 lines. The whole answer. If a reader stops here, did they get the thing?>

## Where the code lives

| Concern | File |
| ------- | ---- |
| ...     | `path/to/file.ts:LINE` |

## <≤4 short sections, each headed by a question or claim>

<Each section: 1 short paragraph + optional list/table. No section >25 lines.>

## What this doc does not cover

<2-4 bullets. Names the adjacent topics and where they live.>

## Cross-references

<Bulleted list. file paths only, no prose.>
```

**No `What is X?` sections, no historical context, no future plans, no comprehensive coverage.** If a fact is in the linked code, link to it instead of restating it.

## Phase 4 — Prose discipline

While drafting, apply the shared skimmability directive (`~/.claude/skills/_shared/skimmable-writing.md`) plus:

- **Code pointers over prose.** "The DO is named `tenantId--userId` at `iq-chat-agent.ts:42`" beats a paragraph explaining the naming.
- **Tables over prose for anything enumerable.** Tools, files, modes, fields → table.
- **No transition paragraphs.** ("Now that we've covered X, let's look at Y" — delete.)
- **No restatements.** If the TL;DR said it, the body doesn't.
- **No defensive hedges.** Cut "it's worth noting that", "in general", "typically", "essentially". The doc's claims should be load-bearing.
- **No tone-setting intros.** ("This document covers..." → delete the sentence.)
- **One mental model per section, max.** If you have two, split sections.

## Phase 5 — Self-review pass

Before declaring done, run two checks:

1. **30-second skim**: read TL;DR + section headings + tables only. Does the reader get the answer to Phase 1's question? If no, the structure is wrong.
2. **Line count**: `wc -l <file>`. Over the cap? Cut until it fits. Don't ask permission to cut.

Common cuts:

- Recap sentences at the top of sections — delete.
- "For example" prose where a table would do — convert.
- Two paragraphs saying the same thing in different words — keep the better one.
- Long lists explaining tradeoffs — collapse to a 2-column table or cut.

Report at the end: doc path, final line count, what was cut from the first draft and why (one line each).

## Guidelines

- **Never write in `iq-ecosystem/docs/narratives/` or any "drafting space" if the doc is single-repo behavior.** Single-repo doc → owning repo's `docs/`, every time. Cross-repo coordination → `iq-ecosystem/docs/coordination/` or similar.
- **Code is the source of truth.** The doc is a reading aid. When in doubt, prefer "see `path:line`" to a re-explanation.
- **Don't write what the linked code already says.** Document the non-obvious: invariants, gotchas, the "why" the code can't show, the cross-cutting picture.
- **One doc, one topic.** Resist the urge to "while I'm here, also cover Y." That's a separate doc.
- **No emojis** unless the user asks.
