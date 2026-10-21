---
name: stage
description: Mechanically stage the invariant-verifiable slice of a working-tree diff and tier the rest into an ordered reading queue. A deterministic classifier (no model verdicts) auto-stages only the SAFE tier — mechanical changes with a checkable invariant (re-export barrels, lockfile+manifest drift) — and orders everything else by blast radius. Use when the user says "stage", "/stage", "what should I read", or is facing a large agent-written diff. Sizing triage (`/triage`) belongs to the triage skill. Nothing semantic is ever auto-staged; there is no reviewer pass here.
---

# Stage

The index is the trust boundary: **staged = mechanically provable, skip it; unstaged = your reading queue.** Everything else comes back in blast-radius order.

## Arguments

None required. `no-stage` — classify and report only; stage nothing.

## Instructions

### Phase 1: Run

Run once from the repo being staged:

```bash
node <skill-base-dir>/scripts/stage.mjs --run
```

Add `--no-stage` when the argument `no-stage` was given. One call classifies, stages the SAFE tier, counts N staged and M left to read, logs the flywheel row (a logging failure only prints a warning), and prints the finished `## Stage` report plus a `jump-queue` block.

The classifier is the single source of truth for tier + risk — never reclassify, promote to SAFE, or soften ESCALATE (disagreements go in the report). A non-zero exit means nothing was staged by this run: report the message and stop.

- **ESCALATE** = high-risk (hot paths, enforcement-config edits, tripwires). **Read first — never staged.**
- **READ / SKIM** = semantic but lower blast radius. Read, in that order.
- **SAFE** = mechanical, invariant-verified. Staged without reading — the only tier that is.

### Phase 2: Jump list

The `jump-queue` block holds one JSON row per queue entry that has a `line` (`tier`, `path`, `line`, `reason`), in reading order. Entries without a `line` (deleted files) are not in it.

Read `~/.claude/skills/_shared/nvim-jump.md`, then make one `nvim-jump` call for the whole list: each row at its `line` with `--note "<TIER>: <what changed and why, one line, from the diff and the coder's handoff>"`. ESCALATE notes lead with the row's `reason`.

### Phase 3: Report

Print the `## Stage` report from the script as is, leading the reply. Add one line per disagreement with a tier. If M is small, say so plainly. Do not recompute N, M or the log row.

### Phase 4: Calibration hook

Bug later found in a mechanically-staged file → `/escape` (`gate_missed=stage`): ground truth on the SAFE invariant. On escape, the class leaves `stage.mjs` until fixed — tiers tighten on evidence, never loosen without it.

## Extending

Per-repo tuning in `.stage.json` (`hotPaths` = the high-risk gate: add contract/data-deletion/freeze paths; `skim` regexes). New SAFE classes live in `scripts/stage.mjs` — each needs a checkable invariant, not a filename pattern. `--json` and `--stage` still work alone for ad-hoc use.
