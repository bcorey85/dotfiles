---
type: "Change"
change_type: "fixed"
title: "plan_check check reads a plan folder through its plan file"
description: "plan_check.py check given a plan folder reads its plan file, as owner already did, in place of crashing with IsADirectoryError."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T03:28:12-06:00"}
seq: 3
kind: "fix"
components: ["script/plan-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_plan_check.py::PlanCheckCliTest::test_check_given_a_plan_folder_reads_its_plan_md_as_the_file_would_be_read"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`check` resolves its path through `plan_format.plan_file_of`. A folder with no plan file exits 1 naming the expected plan-file names, with no traceback.

## Evidence

Judgment from the queued report; the traceback reproduced on an empty folder.

## Result

The new tests get the same exit code and output for the folder as for its `plan.md`, and exit 1 with the expected names for an empty folder.

## Watch

None: a test pins it.

## Back-out

`git revert` the commit.
