---
type: "Change"
change_type: "fixed"
title: "Review ask outcomes with no finding id are logged under a new id"
description: "When a review-loop hands back an ask with no valid finding_id, review_fix.py asks-done and code-step now log the user's answer under a new id instead of dropping it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T23:30:25-05:00"}
seq: 30
kind: "fix"
components: ["script/review-fix", "script/code-step", "script/handback", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_an_ask_without_a_finding_id_is_logged_under_a_new_finding_id_and_reported"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `scripts/review/handback.py`: new `ask_outcome_finding_id(item)`. It returns the ask's own id when it is valid. If
  not, it returns a new 16-hex id in the ledger writer's shape and a stderr note that names the value it ignored.
- `scripts/review/review_fix.py` `asks-done` and `scripts/code/code_step.py` `log_ask_outcomes` both use it. An ask
  with no valid id is now logged, not skipped, and the summary says how many went under a new id. Plan-impact asks
  are still skipped. `skip_reason`, `warn_no_finding_id` and `NO_FINDING_ID` are gone.
- `agents/review-loop.md` ask contract and `skills/_shared/finding-log.md`: the old line said an outcome with no id
  is not logged. They now say it goes under a new id and leaves the loop's ask row open, so never hand back a
  placeholder.

## Evidence

This is the third work sighting of the same class: the review-loop hands back an ask with no real id. The first
two (`none logged`, `none`) got fixes that stopped stray rows by skipping the outcome. The third (agent-ledger LED-28,
`not logged (no id was printed)`) shows that skipping loses the user's answer: the ask outcome never reached the
ledger. Every placeholder seen so far says the loop logged no ask row. So a new id gives the answer its only row.
If a loop did log the row and then lost its id, that row stays open and a second row holds the answer. That is a
smaller error than losing the answer.

The new tests fail on the old scripts: 11 in the review-fix suite, 8 in the code-step ask suite, 3 in the hand-back
suite.

## Result

The three changed test files pass: hand-back 60 of 60, review-fix 118 of 118, code-step asks 15 of 15. Ruff is clean.
The full suite passes except for the real-plan checks, which fail on two agent-ledger plans that are still being
written (LED-46 and LED-48).

## Watch

None. No intake number counts ask outcome rows against ask rows.

## Back-out

Revert the commit.
