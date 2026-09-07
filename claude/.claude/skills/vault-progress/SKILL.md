---
name: vault-progress
description: Weekly capability distillation — measure what the vault actually gained this week, chart it against trajectory.md's named gaps, and decide the next step together. Read-only on trajectory.md unless the user approves an edit in-session. Triggers on "/vault-progress", "what did I learn this week", "am I closing the gap", "weekly progress".
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit, AskUserQuestion]
---

# Vault Progress — did the gap move?

The capability-week counterpart to `/weekly-recap`'s work week. They share nothing — never write work decisions, PR activity, or achievements here.

Vault root: `$VAULT_DIR` if set, else `~/vault`. Target week: the ISO week (Mon–Sun)
containing the argument date if one was given, else today. Label with `date +%G-W%V`.

Idempotent per week — but preserve existing `Direction` answers verbatim.

## The measurement contract — read this before counting anything

`trajectory.md` states the constraint this whole skill lives under:

> Note counts measure exposure, not capability. All nine OSTEP notes exist and none
> of them is understanding. Read the table as "what I have been near," never as
> "what I can do."

So: an **exposure** chart, labeled as one. Never "progress on X" from a count alone.

- **Never call a gap closed from the chart** — only the user closes gaps.
- **Zero is a real reading** — say so plainly, never as a miss.

## Gather (read-only; skip any unavailable source gracefully — never fail the run)

### 1. New notes this week — use the basename set-diff, not `--diff-filter=A`

Vault reorganization defeats `--diff-filter=A` (moves report as new). Diff the **basename sets** instead:

```bash
cd "$VAULT"
BASE=$(git rev-list -1 --before='<monday of target week>' HEAD)
git ls-tree -r --name-only "$BASE"          | sed 's#.*/##' | sort -u > /tmp/vp-old.txt
git ls-tree -r --name-only HEAD -- notes/   | sed 's#.*/##' | sort -u > /tmp/vp-new.txt
comm -13 /tmp/vp-old.txt /tmp/vp-new.txt
```

New = basename existed nowhere at window start (compare `$BASE` against the whole tree — that's what makes moves invisible). Substantially-revised notes (existing basenames, changed content): count only, never itemize.

### 2. The capability chart — count by filename prefix

**Filename prefix is the taxonomy** — match `trajectory.md`'s own method.

```bash
find notes -name '*.md' -printf '%f\n' | sed 's/ - .*//; s/\.md$//' | sort | uniq -c | sort -rn
```

Frontmatter `tags:` are a **cross-check only, never the chart** — on disagreement, report it rather than picking a winner.

Bucket prefixes into the rows below. **Record which prefixes went into each bucket in
the week's entry** — the bucketing is a judgment call.

Rows are read from `trajectory.md` at run time, not hardcoded here:

- Its tag-table capabilities plus its **Named gaps** rows (the closable items; skip **not closing**).

If `trajectory.md`'s capabilities or gap table have changed since the last chart row,
say so and use the new set going forward. Do not retroactively rewrite old rows.

### 3. The trust signal

Count new notes carrying `[unverified]`. Report it as a ratio of the week's new notes.

### 4. Project movement

Per `projects/active/*/` plan file: `next`/`blocked-on` verbatim + steps newly `✓`/`Done`. Never infer status from notes.

Never fabricate. A section with no source material gets `- none`.

## Distill

Three to six bullets on **content**, not counts — what the week's notes are actually about, grouped by learning; name the landed gap or plainly none (off-gap weeks are the most useful report). Then one line: **which gap moved, which didn't, what displaced it** — check `#llms`-crowds-`#backend` specifically.

## Participate — the user steers, the skill never grooms

`trajectory.md` revision is **event-driven only** — this skill **never edits it on its own**. Evidence first, then do what the user says.

1. Present the chart, the delta, and the distillation. Lead with the 1–3 findings that
   would change a decision.
2. Ask **2–3 pointed questions**, via `AskUserQuestion`, each citing the week's
   evidence. Never generic reflection prompts. The good ones sound like:
   - "Four Postgres notes landed and the roadmap step is unmarked — is the step done,
     or did the notes come from setup rather than the step?"
   - "Nothing landed on the gap for three weeks running; the queue's next item is X.
     Re-order the queue, or is the gap wrong?"
   - "This landed as reading, not a build. Does it need a build attached, or is it
     reference that has already done its job?"
3. **Apply nothing without explicit yes**: draft the **exact edit**, show it, apply on approval only. Declined → record in the week's entry, leave `trajectory.md` untouched.
4. Offer `/save-note` for anything surfaced in the conversation that is a fact, and
   `/create-ticket` for anything that is work — never inline into the chart file (derived, evictable; only-copies forbidden).

## Write

Write `<vault>/progress/<ISO year>.md` (create the folder if needed) — one file per
year, matching the `Achievements/<year>.md` precedent.

```markdown
# Progress — <ISO year>

> Exposure chart. Counts measure what I have been near, never what I can do —
> see `trajectory.md`. The distillation below each row is the part that means
> something.

## Chart

| Week     | New | Unver. | DB  | Concur. | Algo | #backend | #devops | #arch | #llms | Moved                    |
| -------- | --- | ------ | --- | ------- | ---- | -------- | ------- | ----- | ----- | ------------------------ |
| 2026-W32 | 8   | 0      | 4   | 0       | 0    | …        | …       | …     | …     | Database internals 0 → 4 |

<gap columns are cumulative totals; New is the week's count. Newest row last.>

## Weeks

### <ISO week> (<Mon date> – <Sun date>)

**New notes** — <basenames, grouped by what they were learning>

**Landed on** — <named gap, or `none of the named gaps` and what it was instead>

**Displaced** — <what got no attention and why, when the evidence shows it>

**Projects** — <`next` / `blocked-on` verbatim per active project; steps marked done>

**Bucketing** — <prefix → row, for this week's counts. Audit trail for the judgment call.>

**Direction** — <each question asked, and the user's answer verbatim. Note any
proposed `trajectory.md` edit and whether it was applied or declined.>
```

Preserve existing `**Direction**` blocks verbatim on re-runs — the compile doesn't own human-authored content.

## Boundaries

- Writes `<vault>/progress/` and nothing else, except a `trajectory.md` edit the user
  explicitly approved in-session.
- **Never writes `cache/`.** Nothing here may be the only copy of anything.
- Never writes `notes/`. A fact surfaced in the conversation goes through `/save-note`.
- Never touches org files, `Weekly/`, or `Achievements/` — those belong to `/vault-review` and
  `/weekly-recap`.
- Log a rule that fights an actual capture to
  `projects/active/vault-redesign/friction.md`. Never redesign the hierarchy mid-run.
- Suggest `vault-sync` at the end if the vault has uncommitted changes.

## Finish

One line: the file path plus the week's headline, e.g.
`~/vault/progress/2026.md — W32: 8 new notes, Database internals 0 → 4, first movement on the gap`.
