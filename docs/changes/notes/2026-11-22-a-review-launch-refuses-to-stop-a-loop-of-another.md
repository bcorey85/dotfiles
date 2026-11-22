---
type: "Change"
change_type: "fixed"
title: "A review launch refuses to stop a loop of another run mode"
description: "review_launch exits with an error naming a live loop of the same repo started in another run mode, and stops only a same-mode loop."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T13:35:58-06:00"}
seq: 29
kind: "fix"
components: ["script/review-launch"]
evidence: ["review-fix-launch-kills-another-review-loop-in-the"]
watches: []
test: "tests/scripts/test_review_launch.py::ReviewLaunchTest::test_a_fix_launch_refuses_a_live_review_loop_and_leaves_it_running"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review_launch.stop_earlier_loops` reads `--skill` from each live loop's saved packet args. A live loop of another run mode stops the launch with its id, mode, pid and the next step, before any folder is made.

## Evidence

/fix launched beside a live /review loop and killed it; the /review relaunch killed the /fix loop in turn. Neither said so first.

## Result

ReviewLaunchTest in `test_review_launch.py`.

## Watch

None.

## Back-out

Revert the commit.
