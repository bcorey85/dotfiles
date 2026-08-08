---
name: vault-progress
description: Weekly capability distillation — measure what the vault actually gained this week, chart it against trajectory.md's named gaps, and decide the next step together. Read-only on trajectory.md unless the user approves an edit in-session. Triggers on "/vault-progress", "what did I learn this week", "am I closing the gap", "weekly progress".
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit, AskUserQuestion]
---

# Vault Progress — did the gap move?

The learning-arc counterpart to `/weekly-recap`. That skill compiles the **work**
week (dailies → decisions, shipped, achievements). This one compiles the **capability**
week: what the vault gained, which named gap it landed on, and what comes next.
They share nothing and must not duplicate each other — never write work decisions,
PR activity, or achievement bullets here.

Vault root: `$VAULT_DIR` if set, else `~/vault`. Target week: the ISO week (Mon–Sun)
containing the argument date if one was given, else today. Label with `date +%G-W%V`.

Idempotent: re-running for the same week rewrites that week's row and entry from the
same sources. The user's answers in an existing entry are preserved verbatim.

## The measurement contract — read this before counting anything

`trajectory.md` states the constraint this whole skill lives under:

> Note counts measure exposure, not capability. All nine OSTEP notes exist and none
> of them is understanding. Read the table as "what I have been near," never as
> "what I can do."

So the chart is an **exposure** chart, labeled as one. It is honest about volume and
silent about competence. Never write "progress on X" from a count alone; write the
count, then ask the question the count cannot answer. If the chart ever reads as a
score, it has become the thing trajectory.md warns about.

Two standing rules follow:

- **Never call a gap closed from the chart.** Only the user closes a gap, against the
  done criteria written under its capability.
- **Zero is a real reading.** A week with no new notes is information about what got
  worked on — commonly a build week, which is the mode that actually teaches. Say so
  plainly; never phrase it as a miss.

## Gather (read-only; skip any unavailable source gracefully — never fail the run)

### 1. New notes this week — use the basename set-diff, not `--diff-filter=A`

The vault gets reorganized. A bulk move makes `git log --diff-filter=A` report every
file in the vault as new — the 2026-08 redesign produced 421 false "new notes" in a
7-day window. Rename detection does not rescue it. Diff the **basename sets** instead:

```bash
cd "$VAULT"
BASE=$(git rev-list -1 --before='<monday of target week>' HEAD)
git ls-tree -r --name-only "$BASE"          | sed 's#.*/##' | sort -u > /tmp/vp-old.txt
git ls-tree -r --name-only HEAD -- notes/   | sed 's#.*/##' | sort -u > /tmp/vp-new.txt
comm -13 /tmp/vp-old.txt /tmp/vp-new.txt
```

A note is new only if its **basename existed nowhere in the vault** at the window
start. Moves, renames into `notes/`, and folder churn all correctly report zero.
(Compare `$BASE` against the whole tree, not just `notes/` — that is what makes a
move invisible.)

Substantially-revised notes are a separate, weaker signal: existing basenames whose
content changed in the window. Report the count only, never itemize — a sync commit
touches files for reasons that are not learning.

### 2. The capability chart — count by filename prefix

**Filename prefix is the taxonomy** (`CLAUDE.md`), and `trajectory.md`'s own "Where I
actually am" table is built this way — `Linux`/`Unix` notes, `DRF` notes, Database
notes. Match that method so the chart is comparable to the baseline already written
down there.

```bash
find notes -name '*.md' -printf '%f\n' | sed 's/ - .*//; s/\.md$//' | sort | uniq -c | sort -rn
```

Frontmatter `tags:` are a **cross-check only, never the chart**. The declared
vocabulary and the real one have diverged: `CLAUDE.md` names six one-per-note tags,
while `notes/` carries ~40 YAML list tags, and `backend`/`architecture` — two of the
four arc capabilities — barely appear as tags at all. Counting capabilities by tag
would report near-zero for the two that matter most. If a cross-check contradicts the
prefix count, report the disagreement rather than picking a winner.

Bucket prefixes into the rows below. **Record which prefixes went into each bucket in
the week's entry** — the bucketing is a judgment call, and writing it down is what
keeps it auditable instead of silently drifting.

Rows are read from `trajectory.md` at run time, not hardcoded here:

- The four arc capabilities in its tag table (`#backend`, `#devops`, `#architecture`,
  `#llms`).
- The rows of its **Named gaps** table — currently Database internals, Concurrency,
  Algorithms/complexity. These are the closable items, so they are the columns that
  earn their place. Skip any gap marked **not closing**.

If `trajectory.md`'s capabilities or gap table have changed since the last chart row,
say so and use the new set going forward. Do not retroactively rewrite old rows.

### 3. The trust signal

Count new notes carrying `[unverified]`. It is the only trust marker in the vault and
no folder carries it anymore, so a week of unmarked hearsay is invisible unless the
chart looks. Report it as a ratio of the week's new notes.

### 4. Project movement

Read the `## Where I am` block at the top of each plan file in
`projects/active/*/`. Report `next` and `blocked-on` verbatim, plus any step heading
that gained a `✓` / `**Done <date>**` line in the window. Never infer status from
which notes exist — that inversion is the exact failure `trajectory.md` records.

Never fabricate. A section with no source material gets `- none`.

## Distill

Three to six bullets, and they must be about **content**, not counts. What are the
week's new notes actually about, grouped by the thing they were learning. Name the
gap each group lands on, or say plainly that it lands on none of them — a week spent
off the named gaps is the single most useful thing this skill can report, and burying
it under a tidy chart is the failure mode to avoid.

Then one line of direction: **which gap moved, which did not, and which was displaced
by what.** `trajectory.md` warns that `#llms` crowds out `#backend` and that a good
evening on the reps lane is not progress on the gap — check for exactly that and say
it when it happened.

## Participate — the user steers, the skill never grooms

`trajectory.md` says revision is **event-driven only. Not on a schedule. Not a weekly
review.** This skill does not violate that, on one condition that is not negotiable:
**it never edits `trajectory.md` on its own.** The user's decision is the event; the
skill's job is to put the evidence in front of him and then do what he says.

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
3. **Apply nothing without an explicit yes.** When an answer implies a
   `trajectory.md` revision — a gap's state moved, a queue item promoted or dropped, a
   capability's done criteria met — draft the **exact edit**, show it, and apply it
   only on approval. If he declines, record the decision in the week's entry and leave
   `trajectory.md` untouched; a declined edit is a real answer, not a loose end.
4. Offer `/save-note` for anything surfaced in the conversation that is a fact, and
   `/create-ticket` for anything that is work. Do not inline them into the chart file —
   the chart is derived and evictable, and an only-copy must never live there.

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

Preserve the `**Direction**` block of any existing week entry verbatim on a re-run —
it is the only human-authored content in the file and the compile does not own it.

## Boundaries

- Writes `<vault>/progress/` and nothing else, except a `trajectory.md` edit the user
  explicitly approved in-session.
- **Never writes `cache/`.** A weekly entry is a log arriving by installment, which is
  precisely what `cache/` rejects. `progress/` is derived and regenerable from git —
  same status as `daily/` — and nothing in it may be the only copy of anything.
- Never writes `notes/`. A fact surfaced in the conversation goes through `/save-note`.
- Never touches org files, `Weekly/`, or `Achievements/` — those belong to `/vault-review` and
  `/weekly-recap`.
- Log a rule that fights an actual capture to
  `projects/active/vault-redesign/friction.md`. Never redesign the hierarchy mid-run.
- Suggest `vault-sync` at the end if the vault has uncommitted changes.

## Finish

One line: the file path plus the week's headline, e.g.
`~/vault/progress/2026.md — W32: 8 new notes, Database internals 0 → 4, first movement on the gap`.
