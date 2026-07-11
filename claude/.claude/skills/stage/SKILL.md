---
name: stage
description: Stage the verifiable majority of a working-tree diff so you read LESS of it. A deterministic classifier gates risk; then an independent Opus reviewer verifies the low-risk files and stages what it clears. The index becomes the trust boundary — staged = verified, skip it; unstaged = your reading queue. Use when the user says "stage", "/stage", "triage", "/triage", "stage the safe stuff", "what should I read", "shoulder the review load", "I'm drowning in this diff", or is facing a large agent-written diff. High-risk files are never auto-staged even when clean; files with findings route to /fix. Complements /review (which reports on everything) by suppressing the verifiable majority so the human queue shrinks.
---

# Stage

The job is to make your reading queue as small as *honestly* possible. The index is the trust boundary:

- **staged** = independently verified — you can skip it (`git diff --staged` to spot-check if paranoid)
- **unstaged** = your reading queue — the residue that couldn't be cleared

A reordered list of all 49 files does not save time; it only reorders the pile. Time is saved only by letting the human *not read* files — which requires a verdict trustworthy enough to sign off unseen. That trust is built two ways, layered:

1. **Deterministic risk gate** (the bundled script) decides *eligibility* to be suppressed. A model verdict can never override it. This is the RADAR premise: risk gates first, calibrated by escape data.
2. **Independent correctness verdict** (an Opus reviewer that did *not* write the code) decides whether an eligible file is actually clean.

A file is suppressed (auto-staged) **only if** it is low-risk by the gate **and** cleared by the reviewer **and** untouched since.

## Guardrails — invariants a model verdict cannot override

- **High-risk is never auto-staged, even when clean.** ESCALATE-tier / hot-path files (row deletion, migrations, auth, CI, removed assertions) warrant human eyes on blast radius alone, independent of correctness. The reviewer judges *is it correct*; the script judges *how bad if it's wrong* — the second is not the model's call.
- **Anything an agent touched lands in your queue.** A file routed to /fix is never auto-staged afterward. Otherwise it's agent-writes → agent-approves → human-never-looks, the exact collusion this skill exists to prevent.
- **The reviewer must out-class the author.** Your code is written by Sonnet ~99% of the time; a same-tier reviewer shares its blind spots. The verify pass uses `code-reviewer-deep` (Opus-pinned) — independent of and stronger than the author. Not self-review.

## Arguments

None required. `no-stage` — run the full pass but stage nothing; just label what *would* be suppressed.

## Instructions

### Phase 0: Is the verify pass even warranted?

If the diff is small enough to read directly (a few files), say so and just classify — don't spend reviewer agents. The verify→suppress machinery is for diffs big enough that reading all of it is the actual problem.

### Phase 1: Classify (deterministic risk gate)

Run the classifier from the repo being staged:

```bash
node <skill-base-dir>/scripts/stage.mjs --json
```

Single source of truth for tier + risk. Do not reclassify, promote into SAFE, or soften an ESCALATE — if you disagree, say so in the report but leave tiers as emitted. If it errors, report and stop.

Each entry carries a `hash` (of its exact diff) and `cachedClean` (a prior run already cleared this identical diff); the output also has a top-level `cacheFile` path. Phases 3 and 4 use these to skip re-review and record verdicts. Note also that the removed-coverage tripwires ("assertions/test cases removed") fire only on *net* removal — a retitled or moved test is not lost coverage — so an ESCALATE on those reasons means coverage genuinely dropped.

The top-level `review` object (`{ files, lines, strategy }`) sizes the reviewer pass — Phase 3 keys the single-vs-fan-out decision on `review.strategy`. And a deleted or renamed module that some surviving file still imports is escalated with a `deleted/renamed module still imported by N file(s)` reason — a build break the correctness reviewer structurally misses (it reads the deleted file's empty diff, never its importers), so the gate catches it instead.

- **ESCALATE** = high-risk. Hot paths (auth, payments, migrations, CI, infra), enforcement-config edits, and tripwires (test skip/only added, assertions/test cases removed, suppressions added, lockfile drift, deleted tests). **Never auto-staged.**
- **READ / SKIM** = low-risk, *eligible* for suppression pending the verify pass.
- **SAFE** = mechanical, invariant-verified (re-export barrels, lockfile+manifest). Staged without review — the model gets no vote here.

### Phase 2: Stage the mechanical SAFE tier

Unless `no-stage`, re-run with `--stage` to stage SAFE. Deterministic, reversible, unchanged from the original design.

### Phase 3: Verify the low-risk majority

First, **drop `cachedClean` files from the review set.** The classifier marks a file `cachedClean` when its diff is byte-identical to a prior run the reviewer already cleared (verdict cache in `<git-dir>/stage-verdicts.json`). Re-reviewing an unchanged file spends Opus tokens to re-derive a verdict you already hold — skip it, carry its prior `clean` verdict forward. This is what makes the `/fix` → re-`/stage` loop cheap: only the files `/fix` actually touched changed hash, so only they get re-reviewed. (A `cachedClean` ESCALATE file still stays in the queue — the cache skips *re-review*, never the tier gate.)

**Pick the review strategy from `review.strategy` in the Phase 1 output — don't override it.** The classifier sets it deterministically: `fan-out` once the review set exceeds ~25 files or ~1500 changed lines, else `single`. A single Opus pass over a large diff is shallow per file, and that shallowness is exactly where a suppressed-tier escape hides — so above the threshold the fan-out is mandatory, not an offer.

- **`single`** — one `code-reviewer-deep` over the whole working diff.
- **`fan-out`** — partition the review set by top-level module/subsystem directory (e.g. `backend/src/modules/validation`, `backend/src/routes`, `frontend/src/features/connectors`, `frontend/src/features/pipeline`) and dispatch one `code-reviewer-deep` per partition. Each returns the same per-file verdict format over its slice. Dispatch concurrently in one message when the partition count is small; use a **Workflow** (one reviewer per partition, fan-out) when there are more partitions than dispatch cleanly in one message. State in the report that a fan-out ran and over which partitions.

Dispatch the reviewer(s) **from the main loop** (they read the git working state). Both agent types below are pinned → **omit `model`**:

- **`code-reviewer-deep`** over its slice (whole diff for `single`, one partition for `fan-out`). Instruct it to return, for *every changed file*, a verdict: `clean` (no correctness or blocking finding) or `findings` (with severity + a one-line each). Emphasize this is Opus reviewing Sonnet-authored code — be adversarial, the whole point is to earn the human's skip. **Hand it the oracle** — the ticket and any eng-spec/plan for this work — and tell it to flag production files that diverge from a locked decision *without a recorded deviation*, not just isolated correctness. Without the spec it can only judge "correct in isolation" and is structurally blind to design drift; the test-intent reviewer catches drift on tests, but nothing catches it on the implementation unless this reviewer has the oracle too.
- **`test-intent-reviewer`** — only if a test file changed. Per changed test file: `pins-intended-behavior` or `weak/bug-pinning` (with the line). A test file is eligible for suppression only if it pins intended behavior. **For any ESCALATE test file flagged with net-removed coverage** ("assertions/test cases removed"), also have it report *where that coverage went*: the specific file/test that now pins the removed assertion, or `COVERAGE-LOST` if nothing does. That mapping is what the human reads the file to confirm — handing it over turns a full read into a spot-check (Phase 6 surfaces it).

### Phase 4: Decision matrix

Per changed file:

| Gate | Reviewer verdict | Action |
|---|---|---|
| low-risk (READ/SKIM) | clean (+ test pins intent, if a test) | **`git add`** — suppressed |
| low-risk | findings | needs-fix bucket — do **not** stage |
| high-risk (ESCALATE) | clean | leave unstaged — flag "cleared, but read anyway (high blast radius)" |
| high-risk | findings | needs-fix bucket |

Never stage a file the reviewers flagged. Never stage across the fix boundary.

**Record verdicts to the cache.** After the matrix, write the verdict cache so the next run can skip re-review of anything untouched. Write JSON to the `cacheFile` path from the Phase 1 output — an object keyed by path: `{ "<path>": { "hash": "<entry.hash>", "verdict": "clean" | "findings" } }`. Use each file's `hash` from the classifier output; set `verdict: "clean"` for files the reviewer cleared (whether suppressed or high-risk-cleared), `"findings"` for anything routed to /fix. Files you skipped as `cachedClean` keep their prior entry — re-emit it. This is the only write to that file; it lives inside `.git` and is never committed.

### Phase 5: Route fixes

Hand the needs-fix bucket to **/fix** with the files + their one-line findings as scope. Do not fix inline — /fix owns the review→commit gates. Fixed files re-enter your queue (never auto-staged), so re-read them after.

### Phase 6: Report

Lead with the queue (what they MUST read), not the suppressed count. Keep it tight — a short queue is the product.

```
## Stage

Read (M) — your queue:
  high-risk, cleared but read anyway:
  - `path`  [test w/ removed coverage: → moved to `target` | ⚠ COVERAGE-LOST]
  routed to /fix (re-read after):
  - `path` — <one-line finding>

Suppressed (N) — verified, skip. `git diff --staged` to spot-check.
```

For each ESCALATE test file with net-removed coverage, append the test-intent reviewer's coverage-migration verdict inline — where the removed assertions now live, or a `⚠ COVERAGE-LOST` flag if they don't. That turns "read the whole file to see what was lost" into "confirm this one mapping." A `COVERAGE-LOST` file is the real read; a "moved to X" file is a spot-check. If a fan-out ran, name the partitions it covered.

If M is small, that IS the win — say so plainly.

### Phase 7: Log the run (flywheel)

Every invocation, append one row to the shared review flywheel so `/audit review` sees staging as a first-class lane and the test-intent runs it now owns:

```bash
bash "$HOME/.claude/skills/review/log-review-metrics" \
  repo="$(basename "$(git rev-parse --show-toplevel)")" lane=stage \
  suppressed=<N staged> queue=<M left to read> routed_fix=<K sent to /fix> \
  test_intent_ran=<0|1> test_intent=<bug-pinning findings> \
  result=<clean|residue>
```

`result=clean` when the queue is empty (everything suppressed or nothing high-risk), else `residue`. If the script fails, mention it and continue — telemetry never blocks. This is the counterpart to the escape data below: `suppressed` is what the skill claimed you could skip; escapes are where that claim was wrong. The ratio is the calibration signal.

### Phase 8: Calibration hook

Any bug later found in a **suppressed** file → `/escape tier=suppressed`. That's the ground truth on whether the reviewer's clean-verdict is trustworthy enough to keep auto-staging. If suppressed-tier escapes climb: tighten (require both reviewers unanimous, drop a file class from eligibility, or narrow the risk gate). Same flywheel as before — relaxation only when escape data supports it, tightening the moment it doesn't.

## Extending

Per-repo tuning in `.stage.json` (`hotPaths`, `skim` regex arrays, merged with defaults). `hotPaths` *is* the high-risk gate — add contract/shared-types, data-deletion, and Phase-0 contract-freeze paths so they can never be suppressed. Mechanical SAFE classes are still added in `scripts/stage.mjs` only — each needs a checkable invariant, not a filename pattern.
