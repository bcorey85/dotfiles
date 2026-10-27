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

1. An `/eng-spec` task dir (`spec.md` decisions, `03-decisions.md` richer ledger plus Direction and Constraints, `02-research.md` facts), from `$ARGUMENTS` or branch/ticket key.
2. A legacy flat plan file (or the old `docs/eng-specs/`).
3. The conversation — design decisions discussed and resolved above.
4. The branch diff — what shipped plus uncovered anti-patterns. Not a code tour: ADR explains the decision, eng-arch the code.
5. The ticket, if one exists.

## Process

1. Apply the gate above. If it stops, stop — no script call.
2. Run `python3 ~/.claude/skills/adr/scripts/adr_flow.py prep "$ARGUMENTS"`. One call resolves the task dir (via `resolve-task-dir.sh`) and prints the ticket key, the absolute target path `docs/decisions/<KEY>-<slug>.md` with any COLLISION flagged, the PR url or `(pending)` (the NORMAL pre-PR case), the ticket URL, the absolute task dir, the path and line count of each source (or the legacy plan, the old-style plan dir, `no spec`, or the ambiguous matches with a rerun command), and the ADR template. It never prints source bodies. Follow the template in full — structure, section line caps, skimmability, mutation discipline. On `AMBIGUOUS` or `COLLISION`, ask the user. On `not a task dir`, ask the user for the right path. On `prep takes one path or ticket key`, ask the user which one they meant. Never invent a URL.
3. Read the listed sources with Read. Add the conversation, the branch diff and the ticket where the sources are thin.
4. Draft honestly and short where sources are thin — but `Alternatives rejected` plus `Assumptions` must be real; unfillable means **ask, never invent.**
5. Write the draft to the target path from `prep`. ADRs never share a directory with plans.
6. Run `python3 ~/.claude/skills/adr/scripts/adr_flow.py finish <draft>` with the flags below. The script checks the header bullets, that every section is filled with no `[placeholder]` left, and the section line caps, then deletes only the task dir. **Task dir was the source means delete all of it, no ask, unless a keep trigger applies** — worth-surviving content goes IN the ADR first.
   - Build the command:
     - Add `--task-dir <absolute task dir from prep>` only when prep printed a `task dir:` line (never for a legacy plan or an old-style plan dir).
     - Add `--keep-task-dir` when prep's "Model still does" line printed it, or the user asks to keep the task dir or says the plan work runs out of order or in parallel. It runs the draft checks, skips every task dir check and the delete, and prints the kept path.
   - Read the outcome:
     - `FAIL`: fix the draft and rerun.
     - `REFUSED delete` for a path problem (the output ends with "Pass the absolute task dir printed by prep"): ask the user for the right path, or rerun without `--task-dir`.
     - `REFUSED delete` for content (anything else): report the reason to the user and never delete by hand. When the refusal names `--keep-task-dir`, offer it. When the refusal says the draft is already committed and unchanged, or that task dir files are newer than the draft, ask the user whether the draft already holds that work, and offer `--draft-is-current`. Pass either flag only when the user picks it. `--draft-is-current` never skips the check for uncommitted task dir changes when the draft is committed.
     - `STOP` (staged entries in the task dir): tell the user to commit or unstage them; never unstage them yourself.
7. Ask the user `Drafted to <path>. Adjust?`. Apply their edits, then run `python3 ~/.claude/skills/adr/scripts/adr_flow.py check <path>` and fix any `FAIL`. `/commit` picks it up.

## Arguments

$ARGUMENTS
