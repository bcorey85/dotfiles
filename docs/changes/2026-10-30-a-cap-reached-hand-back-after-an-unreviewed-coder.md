---
type: "Change"
change_type: "fixed"
title: "A cap-reached hand-back after an unreviewed coder is denied once"
description: "A review loop that caps right after a coder, with no reviewer after it, is sent back once to run a reviewer, including a loop that starts on a handed-in change at iter 0."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T13:25:47-05:00"}
seq: 321
kind: "fix"
components: ["script/handback"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::ReviewerRequiredTest::test_a_cap_after_a_handed_in_change_with_no_reviewer_is_denied_once"
asked: ""
proof: []
unmeasured: "One loop showed it; no intake row counts cap-reached hand-backs whose last step was a coder. A coder resumed by SendMessage is not a recorded step, so a cap after that fix still passes."
---

## Change

`handback.py` `handle_hook` now denies a `cap-reached` packet once when the loop's last recorded step is a coder and the dispatch is not a no-review run. The denial tells the loop to run one reviewer scoped to the coder's files, even at iter 0. A second hand-back from the same agent is no longer denied by this rule and is judged by the transcript gates, so a loop whose reviewer cannot run still exits with the unreviewed files named. This is the smaller Done-when option: the cap keeps its count, and the loop owes one reviewer pass over its own fixer's edits. `review_loop_script.py` is unchanged: it writes its own packets and has no cap-reached path. `review-loop.md` is unchanged, so its opencode port needs no edit.

## Evidence

A review-first loop handed one accepted change ran its fixer, then returned cap-reached at iter 0 with no reviewer dispatched and the single finding `NOT REVIEWED`. The earlier loop had also capped with its last fixer pass unreviewed. Each cap left the commit gate dirty. The prompt's scoped reviewer rule did not stop it, and no hook checked the case.

## Result

Four tests pin it. A coder with no reviewer, the handed-in case, is denied once and the second hand-back is no longer denied by this rule. A coder after the last reviewer is denied once. A reviewer after the last coder passes. A no-review run passes. The two denial tests fail against the previous script: it returned no denial.

## Watch

None: no intake number reads the steps behind a cap-reached hand-back.

## Back-out

Remove `CAPPED_ON_A_FIX_REASON`, the `capped_on_a_fix` block in `handle_hook`, their lines in the module and function docstrings, and the four cap tests.

