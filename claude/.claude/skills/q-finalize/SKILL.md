---
name: q-finalize
description: Collapse a completed QRSPI task folder into a single durable decision record (ADR) and delete the process artifacts (QRSPI step 6 of 6). Runs pre-merge so the record ships in the same PR as the code.
allowed-tools: [Bash, Read, Glob, Grep, Write, Edit, AskUserQuestion]
---

# Finalize QRSPI Task

Collapse a completed QRSPI task folder into one ADR. Delete the scaffolding. Run pre-merge so the ADR ships in the same PR as the code.

## Why

QRSPI ships 6 artifacts to reach implementation. After merge, only the "why" has durable value; the rest rots (research snapshots state-of-code, plans describe done work, structure ordering is dead). This step extracts decisions + alternatives into one ADR, then deletes the scaffolding.

## Folder → File

```
Before:                                          After:
docs/eng-specs/IQ-XXX-name/                      docs/eng-specs/IQ-XXX-name.md
├── IQ-XXX-00-ticket.md
├── IQ-XXX-01-questions.md
├── IQ-XXX-02-research.md
├── IQ-XXX-03-design.md
├── IQ-XXX-04-structure.md
└── IQ-XXX-05-plan.md
```

Folder = in-progress. File = finalized.

## Resolve the task directory

Run the shared resolver (same one used by /q-research, /q-design, /q-structure, /q-plan — do NOT reimplement the logic inline):

```bash
bash ~/.claude/scripts/qrspi-resolve-dir.sh "$ARGUMENTS"
```

Exit 0 → single match, use it. Exit 3 → multiple matches printed, ask the user which. Exit 4 → nothing resolvable, ask for a path. Folder basename is the slug for the output file.

## Inputs

Read FULLY (no limit/offset):

| File                  | Used for                                                    |
| --------------------- | ----------------------------------------------------------- |
| `IQ-XXX-00-ticket.md` | Problem                                                     |
| `IQ-XXX-03-design.md` | Decision, Consequences, Alternatives, Patterns, Constraints |

**Do NOT read** `02-research.md` / `04-structure.md` / `05-plan.md` — design.md distilled them; re-reading adds noise.

Missing `03-design.md` → stop: _"/q-finalize is for completed QRSPI tasks. Run /q-design first, or finalize manually."_

## Detect the PR

| Mode        | When                                          | Command                                                                                                                                                                                   |
| ----------- | --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Live        | Task ticket == current branch                 | `gh pr view --json url,number,title 2>/dev/null`                                                                                                                                          |
| Retroactive | Task ticket ≠ current branch (cleanup branch) | `gh pr list --search "<TICKET>" --state all --json url,number,title,state,mergedAt` — substitute the resolved ticket key (e.g. `IQ-400`), then pick the merged PR matching the task title |

Neither finds → `**PR**: (pending)`. Live mode: run `/q-finalize` **after** `/pr` so the link populates and the ADR commit lands on the same PR. Retroactive works either way.

## Process

1. Resolve task directory, extract slug.
2. Read ticket + design FULLY.
3. Detect PR (live or retroactive).
4. Generate ADR (template below).
5. Write to `docs/eng-specs/IQ-XXX-name.md` (sibling of folder, not inside).
6. Spot-check offer: `Drafted → <path>. Anything to adjust before I delete the folder?`
7. Apply edits, re-offer. On approval, continue.
8. `git rm -r docs/eng-specs/IQ-XXX-name/` — NOT plain `rm`; `git rm` refuses with uncommitted in-flight work.
9. AskUserQuestion (Yes/No): _"Does this change introduce a new pattern or change a subsystem's contract that future readers need to know about?"_
10. Print footer for the answer.

## Decision Record Template

Target **100–140 lines**. Past that, you're including state-of-code material that belongs in eng-arch (Mega-ADR anti-pattern).

### Section rubric

| Section               | Purpose                                                  | Source                                  |
| --------------------- | -------------------------------------------------------- | --------------------------------------- |
| Header                | Status / Ticket / PR / Date — stacked bullets            | metadata                                |
| Problem               | 1–2 paras, technical only (strip story framing)          | `00-ticket.md`                          |
| Decision              | 1–2 paras, what we built                                 | `03-design.md` Decisions                |
| Consequences          | `Easier` + `Watch out for`. Do NOT manufacture downsides | synthesize                              |
| Alternatives rejected | Load-bearing. One option not taken + 1–3 sentences why   | `03-design.md` Alternatives + Reasoning |
| Patterns              | To follow / To avoid — `path:line` refs, minimal prose   | `03-design.md` Patterns                 |
| Constraints           | Limits of approach, what code intentionally does NOT do  | `03-design.md` Constraints              |
| Related               | Eng-arch links — only if eng-arch was updated; else omit | post-/eng-arch                          |

### Discipline

- **Status**: `Accepted` default. `Deprecated` when no longer in force. `Superseded by IQ-YYY` (with link) when replaced. **Once Accepted, do NOT silently edit** — write a new finalize that supersedes. Editing destroys the audit chain.
- **Consequences vs Constraints**: Consequences = what we _accepted_ by deciding. Constraints = rules we worked _within_.
- **No manufactured downsides**: trust `Alternatives rejected` to carry the trade-off load. Thin filler is worse than asymmetry.

### Write for skimmability

Read `~/.claude/skills/_shared/skimmable-writing.md` (single source of truth for the skimmability rules) and apply it in full. ADR-specific additions:

- **One Diátaxis mode**: ADRs are **explanation** (_why_ we decided). Do NOT mix in state-of-code reference — that's eng-arch's job. Cross-link instead.
- **Headings = answers**, ADR flavor: `Status: Accepted` not `Status field`. `FormData Content-Type footgun` not `Implementation note 3`.
- **Per-section line caps** (hard — if you blow it, you're writing the wrong section): Problem ≤ 8. Decision ≤ 8. Consequences ≤ 10. Alternatives ≤ 12. Patterns ≤ 12. Constraints ≤ 8.

### Template

```markdown
# IQ-XXX: [Feature name from ticket]

- **Status**: Accepted
- **Ticket**: [IQ-XXX](jira-url) — from `**URL:**` in ticket.md; if the ticket file records no URL, use the ticket key as plain text (do NOT invent a tracker URL)
- **PR**: [repo#NNN](pr-url) — or `(pending)`
- **Date**: MM-DD-YYYY

## Problem

[1–2 paras]

## Decision

[1–2 paras]

## Consequences

### Easier

- [what this enables / makes faster / safer]

### Watch out for

- [latent risks, ongoing friction, drift, hidden coupling]

## Alternatives rejected

- **[Option]** — [why not, 1–3 sentences]

## Patterns

### To follow

- `path/to/file.ts:42` — [what / why right]

### To avoid

- `path/to/file.ts:99` — [what / why wrong]

## Constraints

- [Non-obvious limit]

## Related

[Omit unless eng-arch updated]

- Eng-arch: `docs/eng-arch/[subsystem].md`
```

## Footer

**Yes** to eng-arch:

```
Saved → docs/eng-specs/IQ-XXX-name.md
Removed → docs/eng-specs/IQ-XXX-name/ (staged via git rm)

Next: /eng-arch docs/eng-specs/IQ-XXX-name.md
ADR-driven mode — scoped, uses the ADR as input, no full codebase sweep.
Commit eng-arch update alongside the ADR so both ship in the same PR.
```

**No** to eng-arch:

```
Saved → docs/eng-specs/IQ-XXX-name.md
Removed → docs/eng-specs/IQ-XXX-name/ (staged via git rm)

Done. /commit picks up both changes.
```

## What NOT To Do

- Read `02-research.md` / `04-structure.md` / `05-plan.md` — distilled, re-reading adds noise.
- Keep any process artifact — the whole point is one durable file.
- Auto-run `/eng-arch` — prompt; most tickets don't need it.
- Exceed ~140 lines — state-of-code belongs in eng-arch.
- Skip user-review before deletion — destructive.
- Use plain `rm` — `git rm -r` stages cleanly and surfaces in-flight work.
- Add an index file — git history + filename pattern is the index.
- Manufacture a downside bullet — trust `Alternatives rejected`.

## Arguments

$ARGUMENTS
