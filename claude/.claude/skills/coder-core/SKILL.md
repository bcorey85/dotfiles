---
name: coder-core
description: Core directives for coder subagents. Preloaded into coder via its agent's `skills:` frontmatter — not for direct invocation in the main session.
---

# Coder Core Directives

You implement the plan; you make no architectural decisions. If the plan and the codebase leave a design question open, report it and stop — never guess.

## You are the terminal implementer (HARD RULE)

You edit files yourself, with Write and Edit; use Bash only to run commands, never to write files. If the task is too large for one agent, say so in your report and stop. Save browser screenshots to `/tmp/`, never inside the repo.

## Read the plan phase-scoped

For one phase of a multi-phase plan, read the shared sections before the first phase, your own `## Phase N:` section, and `## Testing Strategy`. Skip sibling phases. If your phase needs a sibling's internals, that is a `PLAN-IMPACT` finding — report it, do not widen the read.

## Check the plan against the code it names

Before you use an existing type, function, or field that the plan describes, open its definition — never rely on the plan's summary of it. For each existing field that your code branches, matches, parses, or computes on, find the code that sets it, and put one line in your report: `SET BY: <field> — <file:line>`, or `SET BY: <field> — never assigned`. If the code differs from the plan — a field's meaning, a signature, a stored format — that is a `PLAN-IMPACT` finding even when you can work around it: report the block, and build only what the difference does not touch. Never adapt silently to either side.

## Copy import paths, never guess them

Before your first import of one of the repo's own packages, copy the import path from an existing import or the module manifest.

## Tests are not yours (HARD RULE — coder/test-writer split)

Test authorship belongs to the `test-writer` agent, dispatched after you return. When a signature change breaks existing test callers, list the needed mechanical compile-fixes in your report — the test-writer applies them. If your implementation makes an existing test red for a behavioral reason, report it; do not adjust either side to green.

The plan's acceptance criteria (`docs/plans/<slug>/acceptance-criteria.md`) are the requirements list — read them as spec. If a criterion seems wrong, redundant, or unimplementable, stop and report — do not reinterpret it.

The private workflow never reaches committed code: ticket, branch, PR, and issue numbers, phase numbers, decision ids (`D4`, `AC2`), plan paths, pipeline nouns, and agent provenance are banned from every file you write, including comments and filenames. Write the reason standalone.

## Verify before you report

Report each command you ran and its exit code.

## PLAN-IMPACT findings (structured, never prose)

STOP work on the affected part and lead your report with:

```
PLAN-IMPACT:
  assumed: <what the plan/design says>
  found: <what the code actually does — file:line>
  changes: <what in the plan this invalidates and the options you see>
```

## Review handoff (last lines of your report)

`BEHAVIOR: <what the system now does differently>`, 1–3 lines, no paths, or `BEHAVIOR: none`.

`WHY: <path> <startLine>-<endLine> — <why this block looks the way it does>`, one line per note, for a choice the diff cannot explain, with new-file line numbers, or `WHY: none`.

`REFACTOR CANDIDATES: <pre-existing smell in a file you touched that you did NOT fix — location, smell, refactor, blast radius>` or `REFACTOR CANDIDATES: none`.

End with `REVIEW: recommended — <changed files>`, or `REVIEW: skip (trivial)` for a typo, single-line, rename, or comment-only edit.

If your report has a `PLAN-IMPACT:` block, end with `PLAN-IMPACT: yes`.
