---
type: "Change"
change_type: "removed"
title: "The review loop drops the fix-diff verification pass"
description: "Step 5d is gone: no reviewer reads a fix diff that no full review follows, the execution gate is its only read, the loop gate no longer blocks on an unread fix diff, and a review-loop fix finding defers only as an open class member."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T21:59:16-05:00"}
seq: 21
kind: "user-rule"
components: ["agent/review-loop", "script/review-loop-gate", "script/log-review-finding", "shared/finding-log"]
evidence: ["census"]
watches: []
test: ""
asked: "2026-10-25: The check of each fix shows almost nothing at work. - then remove it"
proof: []
unmeasured: ""
---

## Change

- `agents/review-loop.md`: the Step 5d section and every mention of it are gone. The rule is stated where the cap and
  Step 5 end a round: when no full review follows a fix coder, only the execution gate (Step 6) reads its diff. The
  cap exit runs Step 6, then Steps 7 and 7b. A gate repair at the cap runs the gate again with no reviewer pass between.
  Only a `class` finding defers.
- `review_loop_gate.py`: the stop check no longer blocks when a fix coder ran after the last code-reviewer read.
  `PASS_REASON`, `REVIEWERS`, `NO_REVIEW` and the unread and exempt values are gone; `scan` returns
  (ungated, open dispatches). The full-check block is unchanged.
- `log-review-finding` and `skills/_shared/finding-log.md`: the `fix-diff` and `last-pass` sources are gone. A
  deferred review-loop `fix` row needs `source=class`; the logger refuses every other source.
- `docs/rule-anchors.md`: the Step 5d row is gone; the edited review-loop and finding-log blocks carry their new hashes.
- The opencode `review-loop.md` copy drops its Step 5d section and mentions too. It stays stale in other ways.

## Evidence

Work evidence since 2026-10-19: the fix-diff pass filed 31 findings, 27 were fixed, and none was a bug. The pass
costs about 150K cache-read tokens per run. The user read those numbers and asked for the pass to go.

## Result

`test_review_loop_gate.py::test_a_fix_coder_after_the_last_review_needs_only_the_full_check` and
`test_ledger_write.py::test_a_deferred_review_loop_fix_row_is_logged_only_for_an_open_class_member` fail on the base
scripts: the base gate blocks with the unread-fix-diff reason, and the base logger accepts `source=last-pass`. Both pass now. The full suite passes with ruff: 2124 tests in 59 files,
0 failed.

## Watch

None. A watch on bugs that escape a second-round fix needs escape rows tied to the round, which no intake carries.

## Back-out

Revert the commit.
