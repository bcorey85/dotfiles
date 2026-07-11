# /stage Import Checklist

> Everything in this repo that must change in the same PR as pulling the work machine's `/stage` skill in.

## Context

`/preflight` (2026-07-10) is the branch-exit front door: `/stage` deep scan →
lane-scoped `/verify` → read-surface triage → receipt. On machines without
`/stage` it skips the deep-scan tier entirely — it never improvises the Opus
pass. The work machine's `/stage` runs `code-reviewer-deep` + the test-intent
agent (both Opus) and prestages safe hunks; the work loop also REMOVED the
test-intent audit from review-loop convergence (Sonnet-only inner loop, Opus
once at the boundary). This repo still has the loop-side audit, so importing
`/stage` without the edits below double-bills the Opus test-intent pass on
every commit.

## Proposal

Land all of these in one change with the `/stage` import:

- **`claude/.claude/agents/review-loop.md` step 6** — remove the test-intent
  audit block (assertion gate, oracle gate, `test-intent-reviewer` dispatch,
  `test_intent` routing) and the `test_intent` field from the return packet;
  the audit's new home is `/stage`. Keep the MEDIUM `[test-fluff]`/`[test-cull]`
  handling only if `/stage` doesn't own culls — decide at import.
- **`claude/.claude/skills/audit/review.md`** — segment metrics rows by
  `source` (loop rows vs `source=stage` rows) so stage catches don't blend
  into loop stats; re-point test-intent yield math at stage rows. The
  headline number the audit must surface: **marginal catch rate of the Opus
  stage pass over the converged Sonnet loop** — it decides whether the tier
  keeps its bill (≈0 → demote `/stage` to triage-only; high → recalibrate the
  Sonnet reviewer with the caught categories instead).
- **`/stage` itself** — adapt to the interface contract in
  `claude/.claude/skills/preflight/SKILL.md` step 1: findings route through
  `review-loop` (`mode: fix-first`, `caller: fix`, handoff block), every
  catch logs one `log-review-metrics` line with `source=stage` (script
  already accepts arbitrary keys — no script change), returns
  `{catches, prestaged[], residual[]}`. Once `/stage` is installed, its
  prestage half replaces preflight's report-only triage.
- **Propagation sweep** — per project CLAUDE.md: grep `test_intent` /
  `source=stage` consumers (review-loop routing, telemetry calls,
  `audit/review.md`), patch or knowingly skip the opencode agent ports,
  check `-deep` inheritors.

## Open questions

- Does `/stage` own MEDIUM test-cull fixes too, or only the intent audit?
  (Determines how much of review-loop step 6 survives.)
- Ordering inside `/preflight` assumes a monolithic `/stage` invocation at
  step 1 (scan + fixes + prestage before `/verify`); if the work version
  separates scan and prestage, split the invocation accordingly.

## References

- `claude/.claude/skills/preflight/SKILL.md` — step 1 interface contract
- `claude/.claude/agents/review-loop.md:182` — the loop-side test-intent audit to remove
- `claude/.claude/skills/audit/review.md` — yield math to re-point
