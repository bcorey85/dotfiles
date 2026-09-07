---
name: adr
description: Produce a durable decision record (ADR) — sources the "why" from an eng-spec task directory, the conversation, and the branch diff, then collapses the spec scaffolding into the record. Use after shipping a feature that involved a real design decision. Triggers on "/adr", "write an ADR", "record this decision".
allowed-tools: [Bash, Read, Glob, Grep, Write, Edit, AskUserQuestion]
---

# ADR

Covers `/eng-spec` features and small changes with a real decision but no spec.

## Gate: is there a decision here?

An ADR records a DECISION WITH ALTERNATIVES — name one a reasonable engineer might have picked, or stop. No-decision ADRs bury the load-bearing ones.

## Sources (best-first)

1. An `/eng-spec` task dir (`docs/plans/<slug>/`, from `$ARGUMENTS` or branch/ticket key): `spec.md` (decisions), `03-decisions.md` (richer ledger plus Direction and Constraints), `02-research.md` (facts). Resolve via `resolve-task-dir.sh` — never reimplement.
2. A legacy flat plan file (`docs/plans/<KEY>-*.md`, or the old `docs/eng-specs/`).
3. The conversation — design decisions discussed and resolved above.
4. The branch diff — what shipped plus uncovered anti-patterns. Not a code tour: ADR explains the decision, eng-arch the code.
5. The ticket, if one exists.

## Process

1. Apply the gate above.
2. Read `~/.claude/skills/_shared/adr-template.md` and follow it in full —
   structure, section line caps, skimmability, mutation discipline.
3. Detect the PR (`gh pr view`, else `gh pr list --search`, else `(pending)` — the NORMAL pre-PR case). Never wait, never invent a URL; fill the mutable header once it exists.
4. Draft honestly and short where sources are thin — but `Alternatives rejected` plus `Assumptions` must be real; unfillable means **ask, never invent.**
5. Write to `docs/decisions/<KEY>-<slug>.md` (ticket key if any, else the
   `feature/<slug>` branch slug). ADRs never share a directory with plans.
6. **Task dir was the source means delete all of it, no ask.** Worth-surviving content goes IN the ADR first.
7. Spot-check (`Drafted to <path>. Adjust?`), re-offer. `/commit` picks it up.

## Arguments

$ARGUMENTS
