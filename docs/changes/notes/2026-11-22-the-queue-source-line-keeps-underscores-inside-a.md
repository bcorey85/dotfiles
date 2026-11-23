---
type: "Change"
change_type: "fixed"
title: "The queue Source line keeps underscores inside a path"
description: "A ticket's queue Source line keeps underscores and other markdown marks inside its path, so a home folder or slug that holds one still reads as the queue item it names."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T20:17:25-06:00"}
seq: 36
kind: "fix"
components: ["script/plan-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_plan_check.py::PlanCheckCliTest.test_owner_reads_a_home_folder_path_that_holds_an_underscore"
asked: ""
proof: []
unmeasured: "No intake number reads it; the failing test on master is the evidence."
---

## Change

`plan_format.queue_source_line` strips markdown marks only to find the `Source:` label, then takes the value from the raw line and strips marks from the ends of its path word alone, so a backtick-wrapped path followed by text still reads. Before, it removed every `*`, `_` and backtick from the whole line, so a path holding an underscore lost it and no longer matched the home folder or named the right queue file.

## Evidence

After the home-folder spelling fix merged, its test failed on master: the temp home folder's random name held an underscore, which the mark strip removed, so the ticket read as `user`. The test passed in the lane's worktree only because that run's temp name had none.

## Result

The new test (a home folder named `home_dir`, the value wrapped in bold marks) and the earlier home-spelling test fail on the old code (2 failures) and pass now; the 23 tests in test_plan_check.py pass. Full suite passes.

## Watch

None.

## Back-out

Revert the commit: the value goes back to the whole-line mark strip.
