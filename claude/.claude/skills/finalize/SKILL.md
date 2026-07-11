---
name: finalize
disable-model-invocation: true
description: Collapse a completed deep-plan task folder into a single durable decision record (ADR) and delete the process artifacts (deep-plan step 6 of 6). Runs pre-merge so the record ships in the same PR as the code.
allowed-tools: [Bash, Read, Glob, Grep, Write, Edit, AskUserQuestion]
---

# Finalize deep-plan Task

Collapse a completed deep-plan task folder into one ADR. Delete the scaffolding. Run pre-merge so the ADR ships in the same PR as the code.

## Why

deep-plan ships 6 artifacts to reach implementation. After merge, only the "why" has durable value; the rest rots (research snapshots state-of-code, plans describe done work, structure ordering is dead). This step extracts decisions + alternatives into one ADR, then deletes the scaffolding.

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

Run the shared resolver (also used by /deep-plan — do NOT reimplement the logic inline):

```bash
bash ~/.claude/scripts/resolve-task-dir.sh "$ARGUMENTS"
```

Exit 0 → single match, use it. Exit 3 → multiple matches printed, ask the user which. Exit 4 → nothing resolvable, ask for a path. Folder basename is the slug for the output file.

## Inputs

Read FULLY (no limit/offset):

| File                  | Used for                                                    |
| --------------------- | ----------------------------------------------------------- |
| `IQ-XXX-00-ticket.md` | Problem                                                     |
| `IQ-XXX-03-design.md` | Decision, Consequences, Alternatives, Patterns, Constraints |

**Do NOT read** `02-research.md` / `04-structure.md` / `05-plan.md` — design.md distilled them; re-reading adds noise.

Missing `03-design.md` → stop: _"/finalize is for completed deep-plan tasks. Run /deep-plan first, or finalize manually."_

## Detect the PR

| Mode        | When                                          | Command                                                                                                                                                                                   |
| ----------- | --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Live        | Task ticket == current branch                 | `gh pr view --json url,number,title 2>/dev/null`                                                                                                                                          |
| Retroactive | Task ticket ≠ current branch (cleanup branch) | `gh pr list --search "<TICKET>" --state all --json url,number,title,state,mergedAt` — substitute the resolved ticket key (e.g. `IQ-400`), then pick the merged PR matching the task title |

Neither finds → `**PR**: (pending)`. Live mode: run `/finalize` **after you have opened the PR** so the link populates and the ADR commit lands on the same PR. Retroactive works either way.

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

Read `~/.claude/skills/_shared/adr-template.md` and follow it in full — it is the single source of truth for the ADR structure, section line caps, skimmability rules, and mutation discipline (shared with `/adr`, which owns the non-deep-plan lanes).

finalize-specific source mapping:

| Section                                          | Source                                                                          |
| ------------------------------------------------ | ------------------------------------------------------------------------------- |
| Header                                           | metadata + PR detection above                                                   |
| TL;DR                                            | written LAST, distilled from the finished ADR                                   |
| Problem                                          | `00-ticket.md`                                                                  |
| Decision / Alternatives / Patterns / Constraints | `03-design.md`                                                                  |
| Assumptions                                      | `03-design.md` context — record only conditions the decision actually relies on |
| Consequences                                     | synthesize                                                                      |
| Related                                          | only if eng-arch was updated; else omit                                         |

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
