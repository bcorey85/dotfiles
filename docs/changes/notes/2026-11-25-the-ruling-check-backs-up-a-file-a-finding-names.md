---
type: "Change"
change_type: "fixed"
title: "The ruling check backs up a file a finding names by a trailing part"
description: "The review loop's ruling check and its scope guard now share one test of whether a finding names a repo file, so a file named by ./ or a unique trailing part is backed up and can be put back."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T14:59:00-06:00"}
seq: 3
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_finding_naming_a_file_by_a_trailing_part_gets_that_file_backed_up"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

The scope guard kept a fix pass's edit to a file a finding named by `./path` or by a unique trailing part, but the
ruling check backed up only files named in full. A pass the ruling judge put back then left that file edited. Both
now call `script_utils.texts_name_repo_file`.

## Evidence

Judgment from the branch review's read of the two guards.

## Result

The new test backs up `lib/x.py` for a finding that names `x.py`.

## Watch

None: a test pins it.

## Back-out

`git revert` the commit.
