---
type: "Change"
title: "A critical-blocker stop with asks goes through asks-done"
description: "A /code run stopped by a critical blocker that carries asks now takes the user's rulings through asks-done and carries the blockers into one more review, as a cap-reached stop with asks already does."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-28T00:23:28-05:00"}
seq: 163
kind: "fix"
components: ["script/code-step", "script/handback"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_cap_reached.py::CapReachedTest::test_a_critical_blocker_stop_with_an_ask_lets_asks_done_record_it_and_carries_the_blocker_to_one_more_review"
asked: ""
proof: []
unmeasured: "Asks dropped at a blocker stop are not marked in any intake log, so no intake number reads it."
---

## Change

- A critical-blocker packet with asks goes to the asks stage the way a cap-reached packet with asks does: the user
  rules, `asks-done` records the rulings, and the blockers are carried into one more whole-phase review.
- The open-findings check that the cap-reached route used now also treats a critical-blocker review status as open; carried findings now include the packet's blockers. One route serves both stops.
- The second critical-blocker stop of a phase (which stops on `review-blocker`) now lists each packet ask as a
  `- ask: <text> (<file_line>)` line, so the user sees the asks it would otherwise drop.
- The packet parser keeps an ask whose text carries a differently marked list as one ask.

## Evidence

- Read of the stop route: a blocker stop dropped the asks, so `asks-done` found nothing to record.
- The cap-reached route test file holds a blocker case that fails before the change and passes after. The parser
  change has a test with a bullet ask followed by numbered lines at the same indent: the old parser read it as three
  asks, the new one as one. The ask there is a flow mapping, and the test also asserts its `change` is kept and the
  numbered lines join its `question`. A blocker mapping with no question takes the trailing lines into its `finding`.
- A test with a preset `rejected` outcome and two blocker-with-ask packets in a row shows the asks route is taken
  once per phase: the second packet stops on the review blocker instead of looping with no human. The same test
  asserts that second stop prints the ask line.

## Result

- The rulings on a blocker stop are recorded in state, and the blockers reach the next review.

## Watch

No watch: nothing in the intake logs separates asks lost at a blocker stop.

## Back-out

Revert the blocker branch of the review-status stop and the parser change; blocker stops drop their asks again.
