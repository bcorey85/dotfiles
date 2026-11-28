---
type: "Change"
change_type: "fixed"
title: "review launch folds merged-in commits out of an older review base"
description: "A /review given an older --base on a branch that merged master after that base now reviews only the branch's own lines, not the lines master brought in."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T04:49:19-06:00"}
seq: 1
kind: "fix"
components: ["script/review-launch"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_launch.py::ReviewLaunchTest::test_a_launch_base_before_a_merge_leaves_the_merged_in_files_out_of_the_review"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`review/review_launch.py` `resolved_base` returns `merge_free_base.merge_free_base(repo, commit)` instead of the bare commit, as `code/code_review_start.py` already does. A conflicting merged-in parent stops the launch with a `LaunchError` that names the merge; a failing git call stops it with git's error. Nothing is launched.

Three more edits go with it. The `--base` help text in `launch_parser` now says what merge commits after the base brought in is left out. `command_launch` stops with an empty-scope `LaunchError` ("has no changes of its own") when `--base` was given and the merge-free base leaves no changed file, in place of advising "launch with --base <ref>". `code/code_review_start.py` `diff_base` rewords its conflict message (`rstrip('.')`) so the error's own trailing period is not doubled.

## Evidence

On a branch that merged a side branch after its base, `launch --base <older base>` wrote a prompt whose `base:` was the older commit, so the review diff listed the side branch's files as the branch's own.

## Result

The new launch test fails before the change (the diff against the prompt's base lists the merged-in file) and passes after. The conflict test passes and leaves no loop folder. The git-error test shows a failing git call stops the launch with git's error. `test_a_launch_base_whose_only_later_change_is_a_merge_stops_with_an_empty_scope` shows the empty-scope stop.

## Watch

Read the next /review with an old `--base` across a merge for a false conflict stop.

## Back-out

Return `commit.strip()` from `resolved_base` and drop the `merge_free_base` import. Also restore the old `--base` help text, drop the `if base:` empty-scope branch in `command_launch`, and restore the old message in `code_review_start.diff_base`.
