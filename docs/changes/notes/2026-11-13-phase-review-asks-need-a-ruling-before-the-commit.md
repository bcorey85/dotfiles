---
type: "Change"
change_type: "fixed"
title: "Phase review asks need a ruling before the commit"
description: "When a /code phase review hands back reviewer questions, the commit gate refuses the session's `git commit` in that repo until `phase_asks.py rule` records accepted or rejected, with a reason, for each one."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-13T21:25:01-06:00"}
seq: 4
kind: "fix"
components: ["script/review-commit-gate", "script/phase-asks", "script/code-wait", "script/handback-store", "skill/code"]
evidence: ["half-of-the-reviewers-questions-in-a-code-run"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_converged_review_with_phase_asks_not_ruled_on_denies_the_commit_and_names_the_rule_command"
asked: ""
proof: []
unmeasured: "The code skill's converged bullet swaps a hand-typed log call for the `phase_asks.py rule` line that `code_wait.py review` prints. No rule-meter fixture shows a /code fork's converged step, so the wording has no meter run; the commit gate and its tests hold the behavior."
---

## Change

- `code_wait.py review`: when a clean phase packet holds a finding ask, it records a `phase-asks-open` row in the hand-back store and prints the `phase_asks.py rule` line to run. `code_review_start.py` writes `<git dir>/code-phase/run.json` with the lane and phase, which that row carries.
- New `review/phase_asks.py`: `list` prints the open asks and the rule line; `rule '<accepted|rejected>:<one-line reason>' ...` takes one word per ask in order, logs each outcome with `decided_by=session`, and records a `phase-asks-ruled` row. A wrong count, a missing reason or another word exits 2.
- `review_commit_gate.py`: `check_commit` denies while the repo has an open-asks row with no ruling, before the all-clear return. A later review of the repo leaves the asks open; only a ruling settles them. The denial names the rule line.
- New `review/commit_gate_denials.py` holds that denial and the plan-impact denial, moved out of the gate (998 to 978 lines) with its text unchanged.
- `handback_store.py`: the two row kinds, `record_phase_asks_open`, `phase_asks_state` and `unruled_phase_asks`.
- `skills/code/SKILL.md`: the converged bullet runs the printed `phase_asks.py rule` line in place of a hand-typed `log-review-finding` call.

## Evidence

Queue item `half-of-the-reviewers-questions-in-a-code-run`: 332 of 653 reviewer questions in /code runs have no outcome row. The log call was a prose step with nothing checking it.

## Result

The named test fails on the old gate (the commit is allowed) and passes with the change. `tests/scripts/test_phase_asks.py` adds 26 tests; `test_review_commit_gate.py` and `test_code_review_start.py` add 9.

`tests/scripts/test_phase_asks_chain.py` (4 tests) runs the chain as real processes: `code_review_start.py --detach` runs the loop's own entry, which builds the packet and writes the hand-back rows; `code_wait.py review` opens the two asks; the gate hook denies `git commit`; the command the denial prints rules one accepted and one rejected; the gate then passes and both outcome rows hold the asks' finding ids. A ruling with one word for two asks exits 2 and the commit stays denied. A failing ledger leaves the ruling standing. Only the loop's walk is a stand-in (a fixed outcome), so no model call runs. With the telemetry switch off the rows still land: `log-review-finding` writes to the ledger whatever the switch says.

Suite: `bash tests/run.sh` passes, 3867 tests in 142 files, 0 failed.

## Watch

None. `edit_watch.py` has no metric for the share of asks with an outcome row; one needs an intake change.

## Back-out

Revert the commit.

