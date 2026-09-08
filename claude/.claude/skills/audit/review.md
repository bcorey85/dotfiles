# Lane: review — the review flywheel

Analyze both sides of the flywheel:

- **Catches** — what `/review` logs on every run (via `log-review-metrics`): repo, iter, disposition counts (`fix`/`ask`/`nit`/`blocker`), outcome buckets (`fixed`/`skipped_fp`), `test_intent`, `culled`, `comment_noise`, `specialists`, `result`. Rows dated before 2026-09-01 also carry `class_closed` and `fixed_classes`; both are retired and neither is reported — the stopping-rule receipt is prose in the review packet now, not telemetry.
- **Escapes** — what got PAST the gates (via `~/.claude/scripts/log-escape`, fed by `/cc`, `/refactor`, `/verify`, and manual `/escape`): `stage_found`, `gate_missed`, `class`, `severity`.
- **Scans** — what the deterministic scans found and how much was real (via `~/.claude/scripts/log-scan`, fed by `/code` prohibition scans): `scan`, `stage`, `exit`, `candidates`, `confirmed`, `fixed`, `fp`.
- **Plans** — one row per finalized (or abandoned) plan (via `~/.claude/scripts/log-spec-run`, fed by `/eng-spec`): `slug`, `verdict`, `phases`, `criteria`, `decisions`, `research_q`, `gaps`, `falsified`.
- **Per-finding rows** — the same catches at finding granularity (via `~/.claude/skills/review/log-review-finding`, fed by `/review`, `/refactor`, `/verify`, `/branch-recap`): `kind=run` rows carry `gate`, `scope`, `diff_loc`, `n_findings` including the silent runs; `kind=finding` rows carry `gate`, `disposition` (+ optional `blocker`), `class`, `file`, `line`, `actioned`. This is the only source with a per-gate denominator and a `file:line` join key.

Every live row carries `schema_version` (currently `2`); analyze only the current version. Older-schema rows are moved to `~/.claude/telemetry-archive/` and out of scope — `schema_version < current` is the archive filter, no date reasoning.

## Instructions

1. **Locate the files**: `${REVIEW_METRICS_FILE:-$HOME/.claude/review-metrics.jsonl}`, `${REVIEW_ESCAPES_FILE:-$HOME/.claude/review-escapes.jsonl}`, and `${REVIEW_FINDINGS_FILE:-$HOME/.claude/review-findings.jsonl}`. If the metrics file is missing or empty, say so and stop. If only the escapes file is missing, analyze catches and note that no escapes have been logged yet — which is either great news or (more likely, early on) means the capture points haven't fired yet; don't interpret an empty escape log as proof of trustworthiness until catch volume is substantial.

1a. **Per-gate contribution** — read `${REVIEW_FINDINGS_FILE:-$HOME/.claude/review-findings.jsonl}`. Skip with one line if missing or thin. Otherwise, per `gate`:

- **Yield and denominator**: findings per run, and the share of runs with `n_findings=0`. Report the raw pair; read it with the next two before judging.
- **Action rate**: `actioned=fixed` over all its findings. `skipped_fp` is the false-positive rate; `deferred` is the branch-exit queue this gate is feeding.
  **Never rank a queue-output gate by cost-per-`fixed`.** Its `fixed` stays near zero however well it performs; score `1 − skipped_fp/total` and cost per **real** finding (everything not `skipped_fp`) instead.
- **Marginal contribution**: for each finding, whether another gate named the same `file` within ±5 lines in the same branch. Mostly-shared = redundant with the loop; mostly-unique = not, whatever its cost.
- **Yield against `diff_loc`**: bucket runs by reviewed-diff size and report the buckets, never a pooled rate — a weak-looking gate may be reading oversized diffs.
- Keep the `-deep` tiers separate from their base agents throughout.

1b. **Scan precision** — read `${SCAN_RUNS_FILE:-$HOME/.claude/scan-runs.jsonl}`. Skip this step with one line if the file is missing. Only the prohibition and acceptance-stub scans are active; the three whole-tree sweeps that once fed this file are retired, so their rows are history — report them as such and never as a current rate. For each active scan, compute:

- **Precision**: `sum(confirmed) / sum(candidates)`. A scan trending toward zero is training its reader to skim; say so and propose tightening its threshold or retiring it. Report the raw pair, never the ratio alone — 3/4 and 300/400 are not the same evidence.
- **Did-not-run rate**: share of rows with `exit=2`. Any non-trivial rate means the scan is silently absent from runs that reported clean, and every clean report since is suspect.
- Report scan findings BESIDE the agent-gate numbers, never merged into them.

1c. **Residue→escape join** — the price of the one-round cap. Join `actioned=deferred` findings to escapes on **same repo + byte-identical `desc`** (fuzzy is not evidence). Report matches over total deferred as the **residue-leak rate** and list the matched strings. High = deferral leaks and the cap buys speed with defects; near-zero = deferral safe. Skip with one line if either file lacks `deferred` rows.

1d. **Per-class recall** — the only step here that measures what the gates MISS. Everything else in this lane counts what they found, which cannot distinguish a gate that catches everything from one nobody points at. Join the two logs on `class`, current schema era only, and per class report the raw pair:

- **caught** = `kind=finding` rows of that class in `${REVIEW_FINDINGS_FILE}`, listed by the gates that filed them.
- **missed** = rows of that class in `${REVIEW_ESCAPES_FILE}`, listed by `gate_missed`.
- **recall** = caught / (caught + missed), reported with both numbers beside it and never alone.

Read it by class, not by gate — the two sides only meet at the class. Three corrections:

- **Attribute a miss only to a gate that could have caught it.** `gate_missed=eng-spec` rows are plan defects, read them against step 1e instead.
- **A class with zero escapes is not a gate with perfect recall.** Zero escapes with no downstream capture point for the class = recall unmeasured (name the missing capture point), not perfect recall.
- **A class with no value in the logging vocabulary cannot be scored at all.** A domain with no `class` value of its own scores under `other`: report the missing value as an instrument defect, never a recall number.

Headline = the LOWEST-recall class a reviewer owns. Never propose retiring a gate on unmeasured recall; propose the missing capture point first.

1e. **Planning denominator** — read `${SPEC_RUNS_FILE:-$HOME/.claude/spec-runs.jsonl}`. Skip with one line if missing or thin. `gate_missed=eng-spec` escapes are the numerator; this file is the denominator. Report defects per finalized plan AND per criterion (`sum(criteria)` across rows). Report `sum(falsified)` beside them — sweep yield is `falsified / (falsified + eng-spec escapes)`; a yield trending to zero over 10+ plans means the sweep is not running or is checking the wrong claims. Count `verdict=abandoned` rows separately, never drop them.

2. **Aggregate with jq/awk in a single pass** (redirect to a temp file if long). Compute:
   - **Run count** total and per repo. Exclude `lane=stage`, `lane=phase-gate`, and `lane=test-audit` rows from all loop math; they feed only their own metrics below.
   - **Iteration distribution**: runs at `iter=1`, `2`, `3`, `oneshot`. A fat tail at 2–3 means the loop isn't converging first-pass — check whether the same findings recur.
   - **Specialist re-entry distribution**: runs at `spec_iter=0`, `1`, `2`, split by `specialists` — BESIDE the iteration distribution, never summed in. A fat tail at 2 means recurring post-convergence findings; fix upstream in the coder, not a bigger budget.
   - **Disposition totals and per-run averages**: `fix` / `ask` / `nit`, plus `blocker` as a share of `fix`.
   - **False-positive rate**: `sum(skipped_fp) / sum(fixed + skipped_fp + ask)` across runs where triage ran. This is the key calibration signal.
   - **Ask rate**: `sum(ask)` over the same denominator — high means findings are chronically arriving without a decidable correction. Exclude rows carrying `ask_outcome` from every yield denominator here (they are resolutions of an earlier `ask`, not new findings); report their split (`accepted`/`rejected`/`modified`) beside the ask rate instead — rejected-heavy means the gate cries wolf.
   - **Test-intent yield**: firings = rows with `test_intent_ran=1`; findings = sum(`test_intent`). Findings-per-firing, split by `lane` (`phase-gate` = bug-pinning half, `test-audit` = cull + coverage-net + weak half, whose rows also carry `coverage_lost`).
   - **Cull volume**: sum(`culled`) and per-run average — diff-added tests the loop had to delete (`[test-cull]`).
   - **Comment-noise volume**: sum(`comment_noise`) and per-run average — diff-added narration comments the loop deleted.
   - **Specialist firing distribution**: rate of `specialists` = `security` / `perf` / `smell` / combinations / `none (no match)` / `none (suppressed)`.
   - **Smell yield**: on rows with `smell` in `specialists`, sum(`smells`) and findings-per-firing. Compare against `class=smell|duplication` escape volume.
   - **Complexity escapes**: count `class=complexity` rows (logged by `/refactor simplify`) separately from `smell`/`duplication` — Zero rows means the mode has not run — check that before reading the count.
   - **Result distribution**: PASS / PASS WITH WARNINGS / NEEDS CHANGES. Any other value on a pre-2026-09-01 row counts as no-verdict-recorded (the logger rejects them now).
   - **Escapes** (when the escapes file exists): counts by `gate_missed`, by `class`, by `stage_found`; severity mix; per repo; by `lane` (`eng-spec` vs bare `code`); guard-rung distribution, bucketed by `guard` and split by `gate_missed`. Headline per gate: **escape ratio** = its escapes vs. its catch volume over the same period.
   - If a repo filter was passed in arguments, scope everything to that repo.

3. **Interpret** — flag every hit:

| Signal                                              | Threshold            | Action                                                                                                                                                                                                                                       |
| --------------------------------------------------- | -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FP rate                                             | > 30%                | reviewer over-flagging; tighten code-reviewer's "Do NOT Flag" list                                                                                                                                                                           |
| iter tail                                           | > 25% reach iter 3   | convergence problem; check `/fix` skips vs reviewer re-flags                                                                                                                                                                                 |
| nit volume                                          | avg > 4/run          | reporting bar too low                                                                                                                                                                                                                        |
| blocker share                                       | > 15% of `fix`       | flag used for emphasis; re-read its calibration definition against transcripts                                                                                                                                                               |
| test_intent                                         | frequent > 0         | bug-pinning recurring; reinforce spec-first test writing in coders                                                                                                                                                                           |
| culled                                              | not trending to 0    | coders overproducing tests; strengthen `_shared/test-authoring.md` budget. Sustained 0 at healthy volume = budget holds, stages are cheap insurance                                                                                          |
| comment_noise                                       | not trending to 0    | coders shipping narration; strengthen coder-core comment rule                                                                                                                                                                                |
| test-intent yield                                   | ≈ 0 over 10+ firings | tighten trigger at the dead lane's dispatch site (`code` phase gate or `test-audit`) or drop that half                                                                                                                                       |
| specialists                                         | firing ~every run    | trigger effectively always-on; tighten content regexes in `_shared/reviewer-domains.md` (path globs are the omission floor — content first)                                                                                                  |
| drift-gate escapes                                  | recurring            | phase drift gates untrustworthy; raise more phases to `risk: high` until zero                                                                                                                                                                |
| walkthrough / cc / pr-human `class=bug`             | any cluster          | reviewer missing real bugs; check which "Do NOT Flag" rule ate them before reaching for `+deep`                                                                                                                                              |
| pr-bot escapes                                      | recurring class      | fold that class into the in-loop reviewer's domain (the lens runs too late)                                                                                                                                                                  |
| eng-spec escapes                                    | any volume           | never a review miss; remediate upstream in `/eng-spec` only. `plan-drift` clusters = criteria written un-runnable; `bug` clusters = wrong domain model in spec. Healthy shape = caught at phase-gate; arriving at `verify` / pr-human is not |
| walkthrough share of escapes                        | rising               | the skim dial: near-zero at healthy catch volume = walkthrough redundant, skimming safe; rising = walkthrough is load-bearing                                                                                                                |
| guard `none` share, plan-stage rows                 | rising               | finalization sweep waved through. Weight rungs 1–2 (`type` / `convention`); `rule`-heavy = guards parked in prompt budget                                                                                                                    |
| smell / duplication escapes                         | dominating           | smell gate not closing its gap; check its size trigger fires before re-tuning its prompt                                                                                                                                                     |
| escapes ≈ 0 with healthy catches                    | sustained            | gates earning trust; low-risk phase boundaries stay mechanical                                                                                                                                                                               |
| smell yield ≈ 0 over 10+ firings with smell escapes | —                    | specialist prompt or prior-art search too weak; read transcripts before tuning                                                                                                                                                               |
| smell never firing                                  | healthy volume       | 40-added-lines trigger miscalibrated; recheck `_shared/reviewer-domains.md`                                                                                                                                                                  |
| one smell category dominating                       | —                    | strengthen matching coder-core write-time rule (cheaper to prevent)                                                                                                                                                                          |

4. **Report**: a short table of the numbers, then the flags from step 3 (or "calibration looks healthy"). Note the data limitation once: metrics are counts only — refining the reviewer's specific rules requires reading actual review transcripts, not this file.
