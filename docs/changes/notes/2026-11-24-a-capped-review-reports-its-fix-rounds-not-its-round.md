---
type: "Change"
change_type: "changed"
title: "A capped review reports its fix rounds, not its round count"
description: "The review loop's packet carries `fix_rounds` and `post_cap_passes`, a relaunch passes them back through `--fix-rounds` and `--post-cap-passes`, and the code skill reports the `cap reached after N fix round(s)` line as the round count."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-24T15:40:00-06:00"}
seq: 4
kind: "fix"
components: ["skill/code", "script/review-loop-script", "script/review-launch"]
evidence: ["tests/scripts/test_review_loop_script.py", "tests/scripts/test_handback.py", "tests/scripts/test_code_wait.py"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest.test_a_capped_run_lists_its_closure_and_late_repair_read_in_walk_order"
asked: ""
proof: []
unmeasured: "No rule-meter run covers a capped packet: the skill sentence only routes to the packet's line, and the script tests pin the count."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

A capped run's packet holds `fix_rounds` and the kinds of its post-cap passes. `code_wait.py` and `review_fix.py` print `cap reached after N fix round(s); post-cap passes: ...`, and the code skill reports that line as the round count, never `review_round` or `iter`. A later run of the same review starts with `--fix-rounds` and `--post-cap-passes` on its launch line, which `review_launch` writes as header lines the loop reads back.

## Evidence

`test_review_loop_script.py` pins the counts and the relaunch seeding; `test_handback.py` pins the packet keys.

## Result

Before, a capped stop reported the review round or `iter`, which passes the budget after the post-cap passes; now it reports the fix rounds.

## Watch

—

## Back-out

—
