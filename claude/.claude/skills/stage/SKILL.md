---
name: stage
description: Mechanically stage the invariant-verifiable slice of a working-tree diff and tier the rest into an ordered reading queue. A deterministic classifier (no model verdicts) auto-stages only the SAFE tier — mechanical changes with a checkable invariant (re-export barrels, lockfile+manifest drift) — and orders everything else by blast radius. Use when the user says "stage", "/stage", "triage", "/triage", "what should I read", or is facing a large agent-written diff. Nothing semantic is ever auto-staged; there is no reviewer pass here.
---

# Stage

The index is the trust boundary: **staged = mechanically provable, skip it; unstaged = your reading queue.** The classifier's job is to shrink the queue only by what a script can *prove* doesn't need human eyes — and to hand back the rest in blast-radius order so reading time lands where the risk is.

Design decision (2026-07-11): the former verify/suppress tier — an Opus reviewer clearing low-risk semantic files for auto-staging — is removed. A model verdict that licenses the human to skip reading semantic changes trades comprehension for throughput, which is the exact debt the queue exists to surface. The model gets no vote on what you skip; only checkable invariants do.

## Arguments

None required. `no-stage` — classify and report only; stage nothing.

## Instructions

### Phase 1: Classify (deterministic risk gate)

Run the classifier from the repo being staged:

```bash
node <skill-base-dir>/scripts/stage.mjs --json
```

Single source of truth for tier + risk. Do not reclassify, promote into SAFE, or soften an ESCALATE — if you disagree, say so in the report but leave tiers as emitted. If it errors, report and stop. (The output's `hash`, `cachedClean`, `cacheFile`, and `review` fields are legacy from the removed verify pass — ignore them; do not write the verdict cache.)

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

If M is small, say so plainly. If M is large, that is information, not a problem to automate away — it means the diff carries that much semantic change.

### Phase 4: Log the run (flywheel)

Every invocation, append one row to the shared review flywheel:

```bash
bash "$HOME/.claude/skills/review/log-review-metrics" \
  repo="$(basename "$(git rev-parse --show-toplevel)")" lane=stage \
  suppressed=<N staged> queue=<M left to read> result=<clean|residue>
```

`result=clean` when the queue is empty, else `residue`. If the script fails, mention it and continue — telemetry never blocks.

### Phase 5: Calibration hook

Any bug later found in a mechanically-staged file → `/escape` with `gate_missed=stage` (plus the usual `stage_found`/`class`/`severity` fields). That is ground truth on whether a SAFE class's invariant actually holds. On any such escape: the class comes out of `stage.mjs` until the invariant is fixed — mechanical tiers tighten on evidence, never loosen without it.

## Extending

Per-repo tuning in `.stage.json` (`hotPaths`, `skim` regex arrays, merged with defaults). `hotPaths` *is* the high-risk gate — add contract/shared-types, data-deletion, and contract-freeze paths so they always land at the top of the queue. New SAFE classes are added in `scripts/stage.mjs` only — each needs a checkable invariant, not a filename pattern.
