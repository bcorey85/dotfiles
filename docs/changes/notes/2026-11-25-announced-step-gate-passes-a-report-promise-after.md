---
type: "Change"
change_type: "fixed"
title: "Announced-step gate passes a report promise after a background launch"
description: "The Stop hook's announced-step check lets a first-person promise to report on background work (bring back, report, rank, summarize) end the turn when that turn launched the work."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T14:16:43-06:00"}
seq: 3
kind: "fix"
components: ["script/staged-claim-gate"]
evidence: ["queue: staged-claim-gate-false-positive-on-pending"]
watches: []
test: "tests/scripts/test_announced_step.py::AnnouncedStepTest::test_report_step_on_background_work_passes_after_a_launch_and_blocks_without_one"
asked: ""
proof: []
unmeasured: "A Stop-hook false positive with no logged rate; the cost is one extra turn per hit."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- `gates/announced_step.py`: new `REPORT_STEP` words (bring back, report, rank, summarize, collect, compile, relay, combine). A first-person announcement passes when the report word is the announced action itself (within one word of the announcement) and `user_prompts.turn_launched_background` is true for the turn. A report word elsewhere in the sentence ("I'll fix the report parser.") or a second step joined by `and` ("I'll push them and report back.") still blocks.

## Evidence

A turn that launched several background agents ended with "I'll bring back a ranked list" and was sent back as an unstarted step.

## Result

The new tests fail before the change and pass after. A report promise with no launch in the turn, or with the launch in an earlier turn, still blocks.

## Watch

None.

## Back-out

Revert the commit.
