---
type: "Change"
title: "A capped /code review goes on to one more review-loop pass"
description: "A /code review that stops at the round cap takes the user's rulings on its asks, or `review-again` when it has none, and sends the open findings to one more review-loop pass in place of a phase restart."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T17:23:25-05:00"}
seq: 120
kind: "fix"
components: ["script/code-step", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_cap_reached.py::CapReachedTest::test_a_cap_reached_stop_with_an_ask_sends_the_ruling_and_the_open_findings_to_one_more_review_that_converges"
asked: ""
proof: []
unmeasured: ""
---

## Change

- A `cap-reached` packet with asks goes to the asks route. The question lists the open findings, and the review gate
  stays dirty. After `asks-done`, the next review-loop pass gets the rulings as `ruled-asks` and the open findings as
  `carried-findings`, with `iter: 0`. When an ask is accepted, the asks coder runs first, as after any ask. After a
  capped review, the review after the asks coder keeps the whole-phase scope and is never skipped, whether the diff is
  docs only or the asks were already done.
- A `cap-reached` packet without asks stops with stop reason `cap-reached`. `review-again` takes that stop and sends
  the open findings to one more pass. That pass skips the structure pass, which already ran on the same diff.
  `resume` at the stop names `review-again`.
- A phase gets one carried pass. A second cap in the same phase, with or without asks, stops for `start --restart`,
  with no `review-again` and no asks route.
- review-loop passes `carried-findings` to every reviewer.

## Evidence

- In a reported run, `decide adopt` was refused at the cap stop, `resume` asked the user at stage stopped, and
  `review-again` took only an unreadable packet. `start --restart` was the only way on.
- The ten new tests walk cap-reached → ruling → review → converged, the accepted-ask route, `review-again`, and
  `resume`, plus six cases: a docs-only asks coder still gets the review, the review after an asks coder keeps the
  whole-phase scope, the carried findings hold no `ask:` line while the capped round logs its own iter, `review-again`
  skips the structure pass, and a second cap with or without asks stops for a restart. All ten fail on the old script.

## Result

- A capped review goes on with the same diff, so the phase is not started over.

## Watch

—

## Back-out

Revert the commit.
