---
name: adr
description: Produce a durable decision record (ADR) — sources the "why" from an eng-spec task directory, the conversation, and the branch diff, then collapses the spec scaffolding into the record. Use after shipping a feature that involved a real design decision. Triggers on "/adr", "write an ADR", "record this decision".
allowed-tools: [Bash, Read, Glob, Grep, Write, Edit, AskUserQuestion]
---

# ADR

The one decision-record tool. It covers `/eng-spec` features and small changes
where a real decision was made but no spec exists.

## Gate: is there a decision here?

An ADR records a DECISION WITH ALTERNATIVES. The test: can you name at least one
alternative a reasonable engineer might have picked? If the work involved no real
choice (mechanical change, single obvious approach), say so and stop — a trail of
no-decision ADRs buries the load-bearing ones.

## Sources (best-first)

1. An `/eng-spec` task directory (`docs/eng-specs/<slug>/`) passed in
   `$ARGUMENTS` or matching the branch/ticket key. Its `spec.md` holds the
   decisions; `03-decisions.md` is the ledger they were logged into as they were
   resolved (richer than the spec — it carries the `## Direction & Constraints`
   the conversation established); `02-research.md` holds the facts they were made
   against. Resolve it with `~/.claude/scripts/resolve-task-dir.sh` — do NOT
   reimplement the lookup.
2. A legacy flat eng-spec file (`docs/eng-specs/<KEY>-*.md`).
3. The conversation — design decisions discussed and resolved above.
4. The branch diff (merge-base vs default branch) — for `Patterns` `path:line` refs.
5. The ticket, if one exists.

## Process

1. Apply the gate above.
2. Read `~/.claude/skills/_shared/adr-template.md` and follow it in full —
   structure, section line caps, skimmability, mutation discipline.
3. Detect the PR: `gh pr view --json url,number,title` on the current branch;
   else `gh pr list --search "<KEY>" --state all`; else `(pending)`.
4. Draft the ADR. Where a section's source material is thin (common for small
   features), keep it honest and short rather than padding — but
   `Alternatives rejected` and `Assumptions` must be real. If you cannot fill them
   from the sources, **ask the user rather than inventing.**
5. Write to `docs/eng-specs/<KEY>-<slug>.md` (ticket key if any, else the
   `feature/<slug>` branch slug).
6. **If a task directory was the source, collapse it**: the ADR is the durable
   artifact; the scaffolding (`00-ticket.md`, `01-questions.md`, `02-research.md`,
   `03-decisions.md`, `spec.md`) rots. Ask before deleting — the research doc is
   occasionally worth keeping on its own, and only the user knows that.
7. Spot-check offer: `Drafted → <path>. Anything to adjust?` Apply edits,
   re-offer. Then `/commit` picks it up — ship it in the same PR as the code when
   possible.

## Arguments

$ARGUMENTS
