# Lane: review — the review flywheel

Analyze both sides of the flywheel:

- **Catches** — what `/review` logs on every run (via `log-review-metrics`): repo, iter, disposition counts (`fix`/`ask`/`nit`/`blocker`), outcome buckets (`fixed`/`skipped_fp`), `test_intent`, `culled`, `result`. Every row also carries `comment_noise`, always 0 and not reported. Rows dated before 2026-09-01 also carry `class_closed` and `fixed_classes`; both are retired and neither is reported — the stopping-rule receipt is prose in the review packet now, not telemetry.
- **Escapes** — what got PAST the gates (`review_escape` ledger rows via `~/.claude/scripts/telemetry/log-escape`, fed by `/cc`, `/refactor`, `/verify-branch`, and manual `/escape`): `stage_found`, `gate_missed`, `class`, `severity`, `guard`, `path_key`. `path_key` is a keyed hash of the file path, never the path.
- **Scans** — what the deterministic scans found and how much was real (`scan_run` ledger rows via `~/.claude/scripts/telemetry/log-scan`, fed by `/code` prohibition scans): `scan`, `stage`, `exit`, `candidates`, `confirmed`, `fixed`, `fp`.
- **Plans** — one row per finalized (or abandoned) plan (via `~/.claude/scripts/telemetry/log-spec-run`, fed by `/eng-spec`): `verdict`, `phases`, `criteria`, `decisions`, `research_q`, `gaps`, `falsified`.
- **Per-finding rows** — the same catches at finding granularity (via `~/.claude/skills/review/log-review-finding`, fed by `/review`, `/refactor`, `/verify-branch`, `/branch-recap`): `kind=run` rows carry `gate`, `scope`, `diff_loc`, `n_findings` including the silent runs; `kind=finding` rows carry `gate`, `disposition` (+ optional `blocker`), `class`, `path_key`, `line`, `actioned`. `path_key` is a keyed hash of the file path, never the path, so the join key is `path_key:line`. This is the only source with a per-gate denominator and a per-finding join key.

The escapes and scans live in the ledger. On a machine with no `ledger` on PATH, the writers append to `~/.claude/review-escapes.jsonl` and `~/.claude/scan-runs.jsonl` instead. This lane does not read those files.

## Instructions

1. **Locate the rows**: every step below that runs `ledger` first checks `command -v ledger` and, when it is absent, skips the step with one line. Review rows live in the ledger: find them with `ledger query` over `review_run`, `review_finding`, `review_metrics`, `review_escape`, `scan_run` and `spec_run`. For escapes, read `ledger yield --escapes --class all --until <today UTC>` for the per-gate and per-class counts, and `ledger query` over `review_escape` for the rest. If `${REVIEW_ESCAPES_FILE:-$HOME/.claude/review-escapes.jsonl}` exists, add one line: frozen escape history is not migrated until LED-13. If `review_metrics` has no rows, say so and stop. If `review_escape` has no rows, analyze catches and note that no escapes have been logged yet — which is either great news or (more likely, early on) means the capture points haven't fired yet; don't interpret an empty escape log as proof of trustworthiness until catch volume is substantial.

1a. **Per-gate contribution** — read `ledger yield --class all` (per-gate runs, silent runs, findings, `actioned` by a later edit, `dismissed`, `disposed_fixed`) and `ledger query` over `review_finding`. Skip with one line if `ledger` is absent or the rows are thin. Otherwise, per `gate`:

- **Yield and denominator**: findings per run, and the share of runs with `n_findings=0`. Report the raw pair; read it with the next two before judging.
- **Action rate**: `actioned=fixed` over all its findings. `skipped_fp` is the false-positive rate; `deferred` is the branch-exit queue this gate is feeding.
  **Never rank a queue-output gate by cost-per-`fixed`.** Its `fixed` stays near zero however well it performs; score `1 − skipped_fp/total` and cost per **real** finding (everything not `skipped_fp`) instead.
- **Marginal contribution**: for each finding, whether another gate named the same `file` within ±5 lines in the same branch. Mostly-shared = redundant with the loop; mostly-unique = not, whatever its cost.
- **Yield against `diff_loc`**: bucket runs by reviewed-diff size and report the buckets, never a pooled rate — a weak-looking gate may be reading oversized diffs.
- Keep the `-deep` tiers separate from their base agents throughout.

1b. **Scan precision** — read `ledger query` over `scan_run`. Skip this step with one line if `ledger` is absent or the table is empty. Only the prohibition and acceptance-stub scans are active; the three whole-tree sweeps that once fed this file are retired, so their rows are history — report them as such and never as a current rate. For each active scan, compute:

- **Precision**: `sum(confirmed) / sum(candidates)`. A scan trending toward zero is training its reader to skim; say so and propose tightening its threshold or retiring it. Report the raw pair, never the ratio alone — 3/4 and 300/400 are not the same evidence.
- **Did-not-run rate**: share of rows with `exit=2`. Any non-trivial rate means the scan is silently absent from runs that reported clean, and every clean report since is suspect.
- Report scan findings BESIDE the agent-gate numbers, never merged into them.

1c. **Residue→escape join** — the price of the round cap, retired. The join keyed on a byte-identical `desc`, which findings no longer carry. Print one skip line and go on: `residue→escape join: findings carry no desc since LED-5`.

1d. **Per-class recall** — the only step here that measures what the gates MISS. Everything else in this lane counts what they found, which cannot distinguish a gate that catches everything from one nobody points at. Read `ledger yield --recall --class all --until <today UTC>` (skip with one line if `ledger` is absent); it joins the two sides on `class`. Per class report the raw pair:

- **caught** = `review_finding` rows of that class, listed by the gates that filed them: `ledger query "select class, gate, count(*) from review_finding group by class, gate"`. Skip the caught side with one line if `ledger` is absent.
- **missed** = `review_escape` rows of that class, listed by `gate_missed`; the same `--recall` output carries them.
- **recall** = caught / (caught + missed), reported with both numbers beside it and never alone.

Read it by class, not by gate — the two sides only meet at the class. Three corrections:

- **Attribute a miss only to a gate that could have caught it.** `gate_missed=eng-spec` rows are plan defects, read them against step 1e instead.
- **A class with zero escapes is not a gate with perfect recall.** Zero escapes with no downstream capture point for the class = recall unmeasured (name the missing capture point), not perfect recall.
- **A class with no value in the logging vocabulary cannot be scored at all.** A domain with no `class` value of its own scores under `other`: report the missing value as an instrument defect, never a recall number.

Headline = the LOWEST-recall class a reviewer owns. Never propose retiring a gate on unmeasured recall; propose the missing capture point first.

1e. **Planning denominator** — read `ledger query` over `spec_run`. Skip with one line if `ledger` is absent or the rows are thin. The numerator is `eng_spec_escapes` from the `--recall` output of step 1d (the `gate_missed=eng-spec` escapes). Report defects per finalized plan AND per criterion (`sum(criteria)` across rows). Report `sum(falsified)` beside them — sweep yield is `falsified / (falsified + eng-spec escapes)`; a yield trending to zero over 10+ plans means the sweep is not running or is checking the wrong claims. Count `verdict=abandoned` rows separately, never drop them.

2. **Aggregate the `review_metrics` rows** from `ledger query` (skip the step if `ledger` is absent), with jq/awk in a single pass over its output (redirect to a temp file if long). Compute:
   - **Run count** total and per repo. Exclude `lane=stage`, `lane=phase-gate`, and `lane=test-audit` rows from all loop math; they feed only their own metrics below.
   - **Iteration distribution**: runs at `iter=0`, `1`, `2`. A run reaches 2 whenever its first review's `fix` findings got a coder, so 2 is no tail — read it beside the share of runs with `fixed > 0`. Count rows at `3` or `oneshot` apart: they predate the present counter.
   - **Disposition totals and per-run averages**: `fix` / `ask` / `nit`, plus `blocker` as a share of `fix`.
   - **False-positive rate**: `sum(skipped_fp) / sum(fixed + skipped_fp + ask)` across runs where triage ran. This is the key calibration signal.
   - **Ask rate**: `sum(ask)` over the same denominator — high means findings are chronically arriving without a decidable correction. Exclude rows carrying `ask_outcome` from every yield denominator here (they are resolutions of an earlier `ask`, not new findings); report their split (`accepted`/`rejected`/`modified`) beside the ask rate instead — rejected-heavy means the gate cries wolf.
   - **Test-intent yield**: firings = rows with `test_intent_ran=1`; findings = sum(`test_intent`). Findings-per-firing, split by `lane` (`phase-gate` = bug-pinning half, `test-audit` = cull + coverage-net + weak half, whose rows also carry `coverage_lost`).
   - **Cull volume**: sum(`culled`) and per-run average — diff-added tests the loop had to delete (`[test-cull]`).
   - **Smell yield**: sum(`smells`) and findings per run. Compare against `class=smell|duplication` escape volume.
   - **Complexity escapes**: count `class=complexity` rows (logged by `/refactor simplify`) separately from `smell`/`duplication` — Zero rows means the mode has not run — check that before reading the count.
   - **Result distribution**: PASS / PASS_WITH_WARNINGS / NEEDS_CHANGES. Any other value on a pre-2026-09-01 row counts as no-verdict-recorded (the writer now stores an unknown verdict as `other`, counted in the yield header).
   - **Escapes** (`ledger query` over `review_escape`; skip with one line if `ledger` is absent): counts by `gate_missed`, by `class`, by `stage_found`; severity mix; per repo; by `lane` (`eng-spec` vs bare `code`); guard-rung distribution, bucketed by `guard` and split by `gate_missed`. Headline per gate: **escape ratio** = its escapes vs. its catch volume over the same period.
   - If a repo filter was passed in arguments, scope everything to that repo.

3. **Interpret** — flag every hit:

| Signal                                              | Threshold            | Action                                                                                                                                                                                                                                       |
| --------------------------------------------------- | -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FP rate                                             | > 30%                | reviewer over-flagging; name the false-finding class from the transcripts before any suppression rule goes into code-reviewer                                                                                                                |
| nit volume                                          | avg > 4/run          | reporting bar too low                                                                                                                                                                                                                        |
| blocker share                                       | > 15% of `fix`       | flag used for emphasis; the diff reviewer has no blocker definition, so check the tagged lines against what the loop stops a phase for                                                                                                       |
| test_intent                                         | frequent > 0         | bug-pinning recurring; reinforce spec-first test writing in coders                                                                                                                                                                           |
| culled                                              | not trending to 0    | the coder overproducing tests; name the test class from the transcripts before any budget rule goes into `coder-core`. Sustained 0 at healthy volume = the coder's test volume holds |
| test-intent yield                                   | ≈ 0 over 10+ firings | tighten trigger at the dead lane's dispatch site (`code` phase gate or `test-audit`) or drop that half                                                                                                                                       |
| drift-gate escapes                                  | recurring            | phase drift gates untrustworthy; raise more phases to `risk: high` until zero                                                                                                                                                                |
| walkthrough / cc / pr-human `class=bug`             | any cluster          | reviewer missing real bugs; name the missed class from the escape rows before any rule goes into code-reviewer                                                                                                 |
| pr-bot escapes                                      | recurring class      | fold that class into the in-loop reviewer's domain (the lens runs too late)                                                                                                                                                                  |
| eng-spec escapes                                    | any volume           | never a review miss; remediate upstream in `/eng-spec` only. `plan-drift` clusters = criteria written un-runnable; `bug` clusters = wrong domain model in spec. Healthy shape = caught at phase-gate; arriving at `verify` / pr-human is not |
| walkthrough share of escapes                        | rising               | the skim dial: near-zero at healthy catch volume = walkthrough redundant, skimming safe; rising = walkthrough is load-bearing                                                                                                                |
| guard `none` share, plan-stage rows                 | rising               | finalization sweep waved through. Weight rungs 1–2 (`type` / `convention`); `rule`-heavy = guards parked in prompt budget                                                                                                                    |
| smell / duplication escapes                         | dominating           | smell gate not closing its gap; check its size trigger fires before re-tuning its prompt                                                                                                                                                     |
| escapes ≈ 0 with healthy catches                    | sustained            | gates earning trust; low-risk phase boundaries stay mechanical                                                                                                                                                                               |
| smell yield ≈ 0 over 10+ firings with smell escapes | —                    | specialist prompt or prior-art search too weak; read transcripts before tuning                                                                                                                                                               |
| smell never firing                                  | healthy volume       | 40-added-lines trigger miscalibrated; recheck the large-diff rule in `review-loop`                                                                                                                                                            |
| one smell category dominating                       | —                    | strengthen matching coder-core write-time rule (cheaper to prevent)                                                                                                                                                                          |

4. **Report**: a short table of the numbers, then the flags from step 3 (or "calibration looks healthy"). Note the data limitation once: metrics are counts only — refining the reviewer's specific rules requires reading actual review transcripts, not this file.
