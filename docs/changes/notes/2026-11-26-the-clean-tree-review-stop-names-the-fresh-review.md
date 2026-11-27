---
type: "Change"
change_type: "fixed"
title: "the clean-tree review stop names the fresh review base form"
description: "When a review launch on a clean tree has nothing to review, its stop names a fresh `/review base=<ref>` and says a resume launches nothing."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T06:34:05-06:00"}
seq: 13
kind: "fix"
components: ["script/review-launch"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_launch.py::ReviewLaunchTest::test_a_bare_launch_on_a_clean_tree_with_no_base_to_pick_names_the_fresh_review_form"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

The clean-tree `LaunchError` in `review/review_launch.py` `command_launch` now ends: "To review committed work, start a fresh `/review base=<ref>`: a `/review resume` launches nothing when no run is pending."

## Evidence

A session ran `/review resume base=<ref>` after a push deny; the resume ignored the base and replayed, and the stop gave no next form.

## Result

The test fails before the change (the stop does not name the fresh form) and passes after. The skill side, a resume that carries `base=`, is not changed here.

## Watch

Read the next clean-tree stop for a session that retries `/review resume`.

## Back-out

Restore the old ending of the clean-tree `LaunchError`.
