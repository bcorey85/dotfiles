---
name: review-stats
description: Aggregate both sides of the review flywheel — what the gates caught (`~/.claude/review-metrics.jsonl`) and what they missed (`~/.claude/review-escapes.jsonl`) — to compute convergence, false-positive rate, and per-gate escape rates, and flag calibration problems
allowed-tools: [Bash, Read]
---

# Review Stats

Analyze both sides of the flywheel:

- **Catches** — what `/review` logs on every run (via `log-review-metrics`): repo, iter, severity counts, MEDIUM-triage buckets (`fixed`/`skipped_fp`/`ask`), `test_intent`, `result`.
- **Escapes** — what got PAST the gates (via `~/.claude/scripts/log-escape`, fed by `/cc`, `/refactor`, `/q-verify`, and manual `/escape`): `stage_found`, `gate_missed`, `class`, `severity`. This is the ground truth for which gates are trustable.

Both files accumulate counts/categories only — this skill reports distributions and rates, not per-finding patterns.

## Instructions

1. **Locate the files**: `${REVIEW_METRICS_FILE:-$HOME/.claude/review-metrics.jsonl}` and `${REVIEW_ESCAPES_FILE:-$HOME/.claude/review-escapes.jsonl}`. If the metrics file is missing or empty, say so and stop. If only the escapes file is missing, analyze catches and note that no escapes have been logged yet — which is either great news or (more likely, early on) means the capture points haven't fired yet; don't interpret an empty escape log as proof of trustworthiness until catch volume is substantial.

2. **Aggregate with jq/awk in a single pass** (redirect to a temp file if long). Compute:
   - **Run count** total and per repo.
   - **Iteration distribution**: how many runs at `iter=1`, `2`, `3`, `oneshot`. A fat tail at 2–3 means the coder→reviewer loop isn't converging first-pass; look at whether HIGH findings recur.
   - **Severity totals and per-run averages**: critical / high / medium / low.
   - **False-positive rate**: `sum(skipped_fp) / sum(fixed + skipped_fp + ask)` across runs where triage ran. This is the key calibration signal.
   - **Ask rate**: `sum(ask)` over the same denominator — high means MEDIUMs are chronically ambiguous.
   - **Test-intent findings**: total `test_intent` and how many runs had any.
   - **Result distribution**: PASS / PASS WITH WARNINGS / NEEDS CHANGES.
   - **Escapes** (when the escapes file exists): counts by `gate_missed`, by `class`, by `stage_found`; severity mix; per repo; by `lane` when present (lane-level escape rates are the running A/B evidence for /q-plan vs /eng-spec routing). The headline number per gate is the **escape ratio**: escapes attributed to a gate vs. that gate's catch volume over the same period (e.g. `gate_missed=review` escapes vs. total review findings).
   - If a repo filter was passed in arguments, scope everything to that repo.

3. **Interpret** — flag, with thresholds:
   - FP rate **> 30%** → the reviewer is over-flagging; recommend tightening the code-reviewer's "Do NOT Flag" calibration list (cite the rate).
   - **> 25%** of loops reaching iter 3 → convergence problem; recommend checking whether `/fix` is skipping findings or the reviewer re-flags the same issues.
   - Average MEDIUM count **> 4/run** → MEDIUM bar may be too low.
   - Frequent `test_intent > 0` → bug-pinning tests are recurring; worth reinforcing spec-first test writing in the coder agents.
   - **Escape flags** (the trust dial — these decide where human attention stays mandatory):
     - Recurring `gate_missed=drift-gate` → the phase drift gates aren't trustworthy; raise more phases to `risk: high` in plans (restores human phase sign-off) until this trends to zero.
     - `stage_found=cc`/`pr-human` escapes with `class=bug` → the reviewer is missing real bugs, not just smells; check which "Do NOT Flag" suppression rule ate them before assuming `+deep` is the fix.
     - `class=smell|duplication` dominating → the quality layer structurally can't see smells (its calibration suppresses them by design); evidence for a mandatory second-draft/refactor pass, not for re-tuning the reviewer.
     - Escapes ≈ 0 across several features WITH healthy catch volume → gates are earning trust; safe to keep low-risk phase boundaries mechanical.

4. **Report**: a short table of the numbers, then the flags from step 3 (or "calibration looks healthy"). Note the data limitation once: metrics are counts only — refining the reviewer's specific rules requires reading actual review transcripts, not this file.

## Arguments

$ARGUMENTS
