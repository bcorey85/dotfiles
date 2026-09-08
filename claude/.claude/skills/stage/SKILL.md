---
name: stage
description: Mechanically stage the invariant-verifiable slice of a working-tree diff and tier the rest into an ordered reading queue. A deterministic classifier (no model verdicts) auto-stages only the SAFE tier — mechanical changes with a checkable invariant (re-export barrels, lockfile+manifest drift) — and orders everything else by blast radius. Use when the user says "stage", "/stage", "what should I read", or is facing a large agent-written diff. Sizing triage (`/triage`) belongs to the triage skill. Nothing semantic is ever auto-staged; there is no reviewer pass here.
---

# Stage

The index is the trust boundary: **staged = mechanically provable, skip it; unstaged = your reading queue.** Everything else comes back in blast-radius order.

## Arguments

None required. `no-stage` — classify and report only; stage nothing.

## Instructions

### Phase 1: Classify (deterministic risk gate)

Run the classifier from the repo being staged:

```bash
node <skill-base-dir>/scripts/stage.mjs --json
```

Single source of truth for tier + risk — never reclassify, promote to SAFE, or soften ESCALATE (disagreements go in the report). Errors → report and stop. (Ignore legacy `hash`/`cachedClean`/`cacheFile`/`review` fields.)

- **ESCALATE** = high-risk. Hot paths (auth, payments, migrations, CI, infra), enforcement-config edits, and tripwires (test skip/only added, assertions/test cases removed net, suppressions added, lockfile drift, deleted tests, deleted/renamed module still imported). **Read first — never staged.**
- **READ / SKIM** = semantic but lower blast radius. Read, in that order.
- **SAFE** = mechanical, invariant-verified (re-export barrels, lockfile+manifest). Staged without reading — the only tier that is.

### Phase 2: Stage the SAFE tier

Unless `no-stage`, re-run with `--stage`. Deterministic and reversible (`git restore --staged`).

### Phase 3: Report

Lead with the queue in reading order — that IS the product:

```
## Stage

Read (M), in blast-radius order:
  ESCALATE:
  - `path` — <classifier reason>
  READ / SKIM:
  - `path`

Staged mechanically (N) — invariant-verified, skip. `git diff --staged` to spot-check.
```

If M is small, say so plainly.

### Phase 4: Log the run (flywheel)

Every invocation appends one flywheel row:

```bash
bash "$HOME/.claude/skills/review/log-review-metrics" \
  repo="$(basename "$(git rev-parse --show-toplevel)")" lane=stage \
  suppressed=<N staged> queue=<M left to read> result=<clean|residue>
```

`result=clean` on empty queue, else `residue`. Telemetry never blocks.

### Phase 5: Calibration hook

Bug later found in a mechanically-staged file → `/escape` (`gate_missed=stage`): ground truth on the SAFE invariant. On escape, the class leaves `stage.mjs` until fixed — tiers tighten on evidence, never loosen without it.

## Extending

Per-repo tuning in `.stage.json` (`hotPaths` = the high-risk gate: add contract/data-deletion/freeze paths; `skim` regexes). New SAFE classes live in `scripts/stage.mjs` — each needs a checkable invariant, not a filename pattern.
