---
type: "Change"
change_type: "fixed"
title: "the announced-step check passes a step gated on a date, later events or another party"
description: "A step that waits on a date or clock, on later events or on another party's notice no longer blocks a Stop, and a Then or Next step after a gated sentence passes with it."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-27T11:14:07-06:00"}
seq: 2
kind: "fix"
components: ["script/announced-step", "script/staged-claim-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_announced_step.py::AnnouncedStepTest::test_steps_gated_by_a_date_a_clock_later_events_or_another_partys_notice_pass"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

Queue item `stop-hook-blocks-a-reply-whose-next-step-waits-on`. `gates/announced_step.py` gains `TIME_GATE` (`on|by` a weekday or a month and day, `at 4:30`, `at :47`, `tomorrow`, `tonight`, `the next time`), `LATER_EVENT` (`later` and a plural noun), `OTHER_PARTY_RESULT` (`act on their ... notices`) and `CHAINED_STEP` (a sentence opening on Then or Next passes after a gated sentence). Own-step ordering ("at the end", "before starting", "in my final report") still blocks, as do bare promises and a Then or Next after an ungated sentence.

## Evidence

The test above fails on be9a5807d ("I'll run the weekly scan on Nov 29." and "I'll recheck at :47." block there) and passes after. Of the 4 real blocked replies, reply 4 ("later merges") now passes and replies 1-3 still block. Of the 139 flagged sentences, 5 now pass.

## Result

Median hook time over 21 runs (`time_hook.py` on `payload_block.json`): before (be9a5807d) bare Python start 7.7 ms, `staged_claim_gate.py` 43.6 ms; after, bare Python start 7.6 ms, `staged_claim_gate.py` 45.2 ms.

## Watch

None: a test pins it.

## Back-out

`git revert` the commit.
