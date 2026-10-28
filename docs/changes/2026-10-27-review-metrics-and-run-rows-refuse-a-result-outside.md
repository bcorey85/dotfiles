---
type: "Change"
title: "Review metrics and run rows refuse a result outside the verdicts, and a bare word"
description: "log-review-metrics and log-review-finding take result= only from a fixed set and exit 1 on any other value or on an arg with no `=`; a metrics row needs a result; the loop's instructions name the underscore tokens."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T21:30:00-05:00"}
seq: 129
kind: "fix"
components: ["script/log-review-metrics", "script/log-review-finding", "script/refactor-flow", "agent/review-loop", "shared/finding-log"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_log_review_metrics.py::LogReviewMetricsRepoTest::test_an_unquoted_spaced_result_is_refused_and_no_row_is_sent"
asked: "2026-10-27: agent-evals-64 assigned queue item review-loop-metrics-rows-drop-when-result-holds-a"
proof: []
unmeasured: ""
---

## Change

- `_kv.sh`: new `kv_refuse_bare_words` exits 1 on any arg with no `=`. `kv_fold` itself still warns and skips, for
  the other writers.
- `log-review-metrics`: refuses a bare word, and refuses a ledger row whose `result=` is not `PASS`,
  `PASS_WITH_WARNINGS`, `NEEDS_CHANGES`, `NOT_DISPATCHED`, `clean`, `findings` or `residue`, after the existing
  spelling fold. A ledger row with no `result=` is refused too.
- `log-review-finding`: refuses a bare word, and a `kind=run` `result=` that folds to none of the four verdicts.
  It no longer passes an unknown value on to be stored as `other`.
- `refactor_flow.py log`: the run row goes through `log-review-finding --check` before any row is written, so a result
  the writer would refuse fails the log with nothing written.
- `review-loop.md` (and the opencode port), `finding-log.md`: `result=` lists the underscore tokens, which need no
  quoting.

## Evidence

- A review-loop transcript ran `log-review-metrics ... result=NEEDS CHANGES` and `log-review-finding ... result=NEEDS
  CHANGES` unquoted. Both printed `skipping malformed arg (want key=value): CHANGES`, exited 0 and sent `result=NEEDS`,
  which the ledger folds to `other`.
- Six new tests fail on the old scripts: the unquoted split and an unknown result on both writers, a metrics row with
  no result, and a `/refactor` log whose `result` the run-row writer refuses (nothing is written).

## Result

- An unquoted spaced verdict or an unknown verdict exits 1 with a message, and no row is written.

## Watch

—

## Back-out

Revert the commit.
