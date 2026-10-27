---
type: "Change"
title: "code_step test pins a review-loop hand-back that lands after the wait-cap stop"
description: "A test replays the LED-10 run: a review-loop sent a queued SendMessage before the wait-cap stop hands back after it, and `resume` takes that hand-back instead of asking the user."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T09:45:52-05:00"}
seq: 4
kind: "fix"
components: ["script/code-step"]
evidence: ["transcript"]
watches: []
test: "tests/scripts/test_code_step_hand_back.py::HandBackTest::test_a_review_loop_messaged_before_the_wait_cap_that_hands_back_after_it_is_recorded_on_resume"
asked: ""
proof: []
unmeasured: ""
---

## Change

No script change. The code fix is already on master in two commits: ac19cc92 counts the hand-back cap from the launch,
and eb0730b2 makes `review_answer_sent` count a late hand-back. This change adds the test for the case that was
reported, plus a recorded event: `fixtures/hook_event_send_message_queued.json`, the "Message queued for delivery"
response that SendMessage returns when the agent is still running.

## Evidence

The LED-10 transcript shows two dispatches with this shape. Review-loop d5 was printed, the session hit its usage limit,
and the Agent call came 33 hours later. The first `resume` stopped at once, because the cap counted from the dispatch.
Review-loop d6 ran past the 1710 s cap. In both, the fork sent its SendMessage before the stop and the loop handed back
after it. The code back then needed a SendMessage after the stop, so `resume` said "never handed back" and the run fell
back to `review-again`. Run against the scripts from 252eaad4 (the code at the incident), the test fails with that
ask-user. On master it passes.

## Result

`resume` takes the hand-back, marks the phase done and clears `resumableReview`.

## Watch

None.

## Back-out

Revert the commit.
