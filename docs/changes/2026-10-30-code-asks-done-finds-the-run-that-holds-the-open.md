---
type: "Change"
change_type: "changed"
title: "code asks-done finds the run that holds the open asks"
description: "A session with two open /code runs answers review asks in one step: asks-done takes --repo, picks the one run waiting at its asks when the shell is in neither checkout, and the asks hand-back names --repo."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T06:45:22-05:00"}
seq: 331
kind: "fix"
components: ["script/code-step", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_checkout.py::CheckoutTest::test_asks_done_from_outside_two_open_runs_goes_on_with_the_one_run_at_its_asks"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `asks-done` and `correct-ruling` take `--repo <path>` and run in that checkout, which must hold an open run.
- With no `--repo`, two or more open runs and the shell in none of them, `asks-done` goes on with the one run at its
  asks stage. When several runs wait at their asks, it stops, names each checkout and asks for `--repo`.
- The asks hand-back's asks-done line names `--repo <the run's checkout>`.
- The /code skill passes `--repo` through for `asks-done`.

## Evidence

Two sessions ran asks-done from a shell in neither of two open runs' checkouts. The fork stopped, and a retry with the
checkout named worked.

## Result

Targeted tests pass.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit.
