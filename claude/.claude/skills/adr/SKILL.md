---
name: adr
description: Produce a durable decision record (ADR) for features that did NOT go through deep-plan — sources the "why" from an eng-spec doc, the conversation, and the branch diff. Use after shipping a small/medium feature that involved a real design decision. Triggers on "/adr", "write an ADR", "record this decision".
allowed-tools: [Bash, Read, Glob, Grep, Write, Edit, AskUserQuestion]
---

# ADR (non-deep-plan lanes)

`/finalize` produces the ADR for deep-plan tasks by collapsing the task folder. This skill covers everything else — `/eng-spec` features and small changes where a real decision was made but no artifact set exists.

## Gate: is there a decision here?

An ADR records a DECISION WITH ALTERNATIVES. The test: can you name at least one alternative a reasonable engineer might have picked? If the work involved no real choice (mechanical change, single obvious approach), say so and stop — a trail of no-decision ADRs buries the load-bearing ones.

## Sources (best-first)

1. An eng-spec doc path passed in `$ARGUMENTS`, or found under `docs/eng-specs/` matching the branch/ticket key.
2. The conversation — design decisions discussed and resolved above.
3. The branch diff (merge-base vs default branch) — for `Patterns` `path:line` refs.
4. The ticket, if one exists.

If a deep-plan task FOLDER exists for this key, stop and point at `/finalize` instead — it owns that lane and deletes the folder when done.

## Process

1. Apply the gate above.
2. Read `~/.claude/skills/_shared/adr-template.md` and follow it in full — structure, section line caps, skimmability, and mutation discipline.
3. Detect the PR the same way `/finalize` does: `gh pr view --json url,number,title` on the current branch; else `gh pr list --search "<KEY>" --state all`; else `(pending)`.
4. Draft the ADR. Where a section's source material is thin (common for small features), keep the section honest and short rather than padding — but `Alternatives rejected` and `Assumptions` must be real; if you cannot fill them from the sources, ask the user rather than inventing.
5. Write to `docs/eng-specs/<KEY>-<slug>.md` (ticket key if any, else `feature/<slug>` branch name slug).
6. Spot-check offer: `Drafted → <path>. Anything to adjust?` Apply edits, re-offer. Then done — `/commit` picks it up; ship it in the same PR as the code when possible.

## Arguments

$ARGUMENTS
