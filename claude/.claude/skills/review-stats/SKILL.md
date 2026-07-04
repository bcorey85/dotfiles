---
name: review-stats
description: Aggregate the review-fix loop metrics in `~/.claude/review-metrics.jsonl` — iteration distribution, severity counts, false-positive rate, test-intent findings — and flag calibration problems
allowed-tools: [Bash, Read]
---

# Review Stats

Analyze the metrics that `/review` logs on every run (via `log-review-metrics`). The JSONL accumulates counts only — repo, iter, severity counts, MEDIUM-triage buckets (`fixed`/`skipped_fp`/`ask`), `test_intent`, and `result` — so this skill reports distributions and rates, not per-finding patterns.

## Instructions

1. **Locate the file**: `${REVIEW_METRICS_FILE:-$HOME/.claude/review-metrics.jsonl}`. If missing or empty, say so and stop — there's nothing to analyze until `/review` has logged some runs.

2. **Aggregate with jq/awk in a single pass** (redirect to a temp file if long). Compute:
   - **Run count** total and per repo.
   - **Iteration distribution**: how many runs at `iter=1`, `2`, `3`, `oneshot`. A fat tail at 2–3 means the coder→reviewer loop isn't converging first-pass; look at whether HIGH findings recur.
   - **Severity totals and per-run averages**: critical / high / medium / low.
   - **False-positive rate**: `sum(skipped_fp) / sum(fixed + skipped_fp + ask)` across runs where triage ran. This is the key calibration signal.
   - **Ask rate**: `sum(ask)` over the same denominator — high means MEDIUMs are chronically ambiguous.
   - **Test-intent findings**: total `test_intent` and how many runs had any.
   - **Result distribution**: PASS / PASS WITH WARNINGS / NEEDS CHANGES.
   - If a repo filter was passed in arguments, scope everything to that repo.

3. **Interpret** — flag, with thresholds:
   - FP rate **> 30%** → the reviewer is over-flagging; recommend tightening the code-reviewer's "Do NOT Flag" calibration list (cite the rate).
   - **> 25%** of loops reaching iter 3 → convergence problem; recommend checking whether `/fix` is skipping findings or the reviewer re-flags the same issues.
   - Average MEDIUM count **> 4/run** → MEDIUM bar may be too low.
   - Frequent `test_intent > 0` → bug-pinning tests are recurring; worth reinforcing spec-first test writing in the coder agents.

4. **Report**: a short table of the numbers, then the flags from step 3 (or "calibration looks healthy"). Note the data limitation once: metrics are counts only — refining the reviewer's specific rules requires reading actual review transcripts, not this file.

## Arguments

$ARGUMENTS
