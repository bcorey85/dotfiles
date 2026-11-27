---
type: "Change"
change_type: "removed"
title: "review fork review-stop.md read-first line withdrawn"
description: "The review-fork-run.md line that read an existing review-stop.md before the Write is withdrawn; no skill line ships for it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T03:50:23-06:00"}
seq: 6
kind: "fix"
components: ["skill/review"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_toolkit_prose_facts.py::ToolkitProseFactsTest::test_review_fork_run_has_its_six_sections_and_calibration_drops_the_silent_failure_line"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

The read-first line added to review-fork-run.md's ending step in ac54ddab0 is removed, with its prose test, its rule-anchors row change and its change note. review-fork-run.md is back to its text at 3ce76f922.

## Evidence

Judgment, the orchestrator's ruling: a skill line waits on rule-meter runs. The cause is a stale review-stop.md from an earlier run that stays in the run folder, so the fix belongs on the launch side and goes to the review-launch lane.

## Result

review-fork-run.md matches 3ce76f922; the existing section test still passes.

## Watch

-

## Back-out

`git revert` the commit.
