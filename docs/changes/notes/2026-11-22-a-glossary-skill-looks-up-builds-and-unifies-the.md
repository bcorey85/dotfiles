---
type: "Change"
change_type: "added"
title: "A /glossary skill looks up, builds and unifies the project's domain terms"
description: "A new /glossary skill answers whether a term exists and what it means, builds docs/glossary.md from the code on request, and lists concepts the code names more than one way with a proposed canonical name."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T11:00:05-06:00"}
seq: 13
kind: "user-rule"
components: ["skill/glossary"]
evidence: ["user request"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: "Rule-meter runs pending: no meter scenario grades a slash-command lookup or a glossary build yet, so the skill stays uncommitted until it runs or the user rules on shipping it unmeasured. No intake number reads it."
---

## Change

New `skills/glossary/SKILL.md` with three modes:

- lookup: finds any `*glossary*.md`, matches the term with its word forms and aliases, and checks the code; answers
  defined, alias, in code only, or nowhere, with `file:line`.
- `setup`: when no glossary exists, scans models, API surface, service verbs and docs, and writes `docs/glossary.md` as
  one `##` heading per domain area and one `###` heading per term (kind, the defining symbol and file with no line
  number, one-sentence meaning, an `Avoid:` line listing only aliases the repo uses), never a Markdown table (user request, 2026-11-22). A word gets an entry only when it has an alias in use, two meanings, or a meaning the name does
  not show; the glossary is vocabulary, not a code map (user request, 2026-11-22). An existing glossary is never overwritten, and entries added to it keep its
  own format (user request, 2026-11-22). A run that
  creates the glossary appends a one-line pointer to the repo's root `CLAUDE.md` when that file exists (user request, 2026-11-22). The
  pointer is a `## Domain language` section: canonical names only, look up unsure terms, and no new domain term
  without the user's approval (user request, 2026-11-22).
- `drift`: lists synonyms, verb drift, layer drift, overloaded words and stale entries, each confirmed at both names,
  with use counts and a canonical pick; renames go to `/refactor`.

The skill works with no glossary file and writes to the repo only in `setup`, which the user starts, so no repo has
to change.

## Evidence

user request.

## Result

Pending rule-meter runs.

## Watch

None: see `unmeasured`.

## Back-out

Delete `skills/glossary/`.
