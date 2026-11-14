---
type: "Change"
change_type: "fixed"
title: "Review loop: an ask the session rejected is dropped when a later round raises it again"
description: "asks-done records each rejected ask (file:line and question) in the hand-back store; the loop reads them at start and files a repeat under dropped asks with a reason that says it was already rejected, instead of stopping on it."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-13T15:00:00-06:00"}
seq: 4
kind: "fix"
components: ["script/review-fix", "script/review-loop", "script/handback-store"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_an_ask_the_session_rejected_comes_back_as_a_dropped_ask_not_a_stop"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/handback_store.py` gains `record_rejected_ask` and `rejected_ask_texts` (an `ask-rejected` row scoped to the
reviewed repo). `review_fix_asks.py` `record_rejected_asks` writes one per ask answered rejected, once per packet.
`review_loop_main.build_loop` reads them through `review_loop_ruled.rejected_ask_records`, and `drops_repeated_ask` (and `without_rejected`, for
`[design-decision]` fixes in `split_review`) drops an ask on the same file whose question (the text before its `change:` part, as stored) has a near title
(`review_loop_findings.repeats_a_rejected_ask`, built on `near_title`) into the packet's dropped asks under
`REJECTED_ASK_REASON`. asks-done writes under the `--repo` of the packet it answers (`packet_repo`), and the loop reads
under the top level of the repo it reviews, so both key on the same repo. `asks-done --correct` records a new rejection
and withdraws a rejection the correction undoes (`ask-rejection-withdrawn`).

## Evidence

judgment: one ask was raised four times across a phase loop and a branch-review fix loop after each resume answered
rejected, and each round stopped on it again.

## Result

The new tests fail without the change and pass.

## Watch

None: a routing fix with a fixed outcome.

## Back-out

Revert the commit.
