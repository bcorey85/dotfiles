# Lane: review — the review flywheel

Analyze both sides of the flywheel:

- **Catches** — what `/review` logs on every run (via `log-review-metrics`): repo, iter, severity counts, MEDIUM-triage buckets (`fixed`/`skipped_fp`/`ask`), `test_intent`, `culled`, `comment_noise`, `specialists`, `result`.
- **Escapes** — what got PAST the gates (via `~/.claude/scripts/log-escape`, fed by `/cc`, `/refactor`, `/verify`, and manual `/escape`): `stage_found`, `gate_missed`, `class`, `severity`. This is the ground truth for which gates are trustable.
- **Second drafts** — what coders' own sweeps caught in their first drafts (logged by `/code` and `/fix` from each report's `SECOND DRAFT:` line): `source`, `coder`, `second_draft` (clean/found/missing), `categories`, `text`. This is the evidence base for tuning `coder-core` — the smells first drafts reliably ship.

The metrics and escapes files accumulate counts/categories only; the second-draft file also carries the receipt text, but this lane aggregates its categories — read the raw file directly when you need the actual receipts.

## Instructions

1. **Locate the files**: `${REVIEW_METRICS_FILE:-$HOME/.claude/review-metrics.jsonl}`, `${REVIEW_ESCAPES_FILE:-$HOME/.claude/review-escapes.jsonl}`, and `${SECOND_DRAFT_FILE:-$HOME/.claude/second-draft.jsonl}`. If the metrics file is missing or empty, say so and stop. A missing second-draft file just means no `/code`/`/fix` dispatches since it was wired — note it and move on. If only the escapes file is missing, analyze catches and note that no escapes have been logged yet — which is either great news or (more likely, early on) means the capture points haven't fired yet; don't interpret an empty escape log as proof of trustworthiness until catch volume is substantial.

2. **Aggregate with jq/awk in a single pass** (redirect to a temp file if long). Compute:
   - **Run count** total and per repo.
   - **Iteration distribution**: how many runs at `iter=1`, `2`, `3`, `oneshot`. A fat tail at 2–3 means the coder→reviewer loop isn't converging first-pass; look at whether HIGH findings recur.
   - **Severity totals and per-run averages**: critical / high / medium / low.
   - **False-positive rate**: `sum(skipped_fp) / sum(fixed + skipped_fp + ask)` across runs where triage ran. This is the key calibration signal.
   - **Ask rate**: `sum(ask)` over the same denominator — high means MEDIUMs are chronically ambiguous.
   - **Test-intent yield**: firings = runs with `test_intent_ran=1`; findings = sum(`test_intent`). Report findings-per-firing. Rows lacking `test_intent_ran` (and `iter=oneshot` rows) predate the 2026-07 schema — exclude them from yield math.
   - **Cull volume**: sum(`culled`) and per-run average — diff-added tests the loop had to delete (`[test-fluff]` + `[test-cull]`). Rows lacking the field predate the 2026-07-10 wiring; exclude them.
   - **Comment-noise volume**: sum(`comment_noise`) and per-run average — diff-added narration comments the loop deleted. Same schema date and exclusion as `culled`.
   - **Specialist firing distribution**: rate of `specialists` = `security` / `perf` / both / `none (no match)` / `none (suppressed)`. Rows lacking the field predate the 2026-07 specialist split — exclude them.
   - **Result distribution**: PASS / PASS WITH WARNINGS / NEEDS CHANGES.
   - **Escapes** (when the escapes file exists): counts by `gate_missed`, by `class`, by `stage_found`; severity mix; per repo; by `lane` when present (`eng-spec` vs bare `code` — i.e. whether the work was specced at all; rows logged before 2026-07-13 carry retired `deep-plan`/`q-plan` labels and should be folded into `eng-spec`). The headline number per gate is the **escape ratio**: escapes attributed to a gate vs. that gate's catch volume over the same period (e.g. `gate_missed=review` escapes vs. total review findings).
   - **Second drafts** (when the file exists): dispatch count; rate of `clean` / `found` / `missing`; category distribution across `found` receipts (overall and per `coder` type); per repo, per `source` (code vs fix), and per `lane` when present.
   - If a repo filter was passed in arguments, scope everything to that repo.

3. **Interpret** — flag, with thresholds:
   - FP rate **> 30%** → the reviewer is over-flagging; recommend tightening the code-reviewer's "Do NOT Flag" calibration list (cite the rate).
   - **> 25%** of loops reaching iter 3 → convergence problem; recommend checking whether `/fix` is skipping findings or the reviewer re-flags the same issues.
   - Average MEDIUM count **> 4/run** → MEDIUM bar may be too low.
   - Frequent `test_intent > 0` → bug-pinning tests are recurring; worth reinforcing spec-first test writing in the coder agents.
   - `culled` not trending toward 0 across runs → coders are still overproducing tests and the loop is paying to delete them; strengthen coder-core's write-time test budget (cite the average). Sustained `culled=0` with healthy run volume → the budget holds; the cull stages are cheap insurance, not load-bearing.
   - `comment_noise` not trending toward 0 → the second-draft sweep isn't deleting narration comments; strengthen that sweep item in coder-core (same logic as `culled`).
   - Test-intent yield ≈ 0 over **10+ firings** → the stage fires but finds nothing; tighten its trigger in `review/SKILL.md` or drop it. (General pattern: any always-on stage needs a `*_ran` field so yield-per-firing stays computable.)
   - Specialists firing on **~every** run over healthy volume → the deterministic trigger is effectively always-on; if the extra passes' cost matters, tighten the content regexes in `_shared/reviewer-domains.md` (the path globs are the omission-coverage floor — tighten content first).
   - **Escape flags** (the trust dial — these decide where human attention stays mandatory):
     - Recurring `gate_missed=drift-gate` → the phase drift gates aren't trustworthy; raise more phases to `risk: high` in plans (restores human phase sign-off) until this trends to zero.
     - `stage_found=cc`/`pr-human` escapes with `class=bug` → the reviewer is missing real bugs, not just smells; check which "Do NOT Flag" suppression rule ate them before assuming `+deep` is the fix.
     - `class=smell|duplication` dominating → the quality layer structurally can't see smells (its calibration suppresses them by design); evidence for a mandatory second-draft/refactor pass, not for re-tuning the reviewer.
     - Escapes ≈ 0 across several features WITH healthy catch volume → gates are earning trust; safe to keep low-risk phase boundaries mechanical.
   - **Second-draft flags** (the coder-core tuning dial):
     - One category dominating `found` receipts (say **> 40%**) → first drafts reliably ship that smell; recommend strengthening the matching `coder-core` rule (cite the category and rate) — this is the same evidence loop `skipped_fp` provides for the reviewer.
     - `missing` rate **> 10%** → coders are skipping the sweep receipt; the orchestrators should be treating those reports as unfinished, so check whether `/code`/`/fix` are actually enforcing it.
     - `clean` rate **> 85%** WHILE escapes show `class=smell|duplication` → the sweep is rubber-stamping, not sweeping (coder-core presumes first drafts smelly); recommend reinforcing the sweep's checklist rather than trusting the clean receipts.

4. **Report**: a short table of the numbers, then the flags from step 3 (or "calibration looks healthy"). Note the data limitation once: metrics are counts only — refining the reviewer's specific rules requires reading actual review transcripts, not this file.
