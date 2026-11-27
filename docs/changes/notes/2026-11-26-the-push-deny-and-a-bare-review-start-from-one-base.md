---
type: "Change"
change_type: "fixed"
title: "the push deny and a bare review start from one reviewed base"
description: "The push gate's unreviewed deny and a bare /review on a clean tree now both name the newest recorded reviewed base that is a strict ancestor of HEAD, so a base equal to HEAD or off the branch is skipped for an older one."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T09:10:00-06:00"}
seq: 14
kind: "fix"
components: ["script/git-discipline-gate", "script/review-launch"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_launch.py::ReviewLaunchTest::test_a_bare_launch_skips_a_recorded_base_that_is_head_itself_for_an_older_one"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`lib/reviewed_tree.py` `latest_reviewed_base` is replaced by `newest_reviewable_base`: the newest base in the shared reviewed-bases record that is an ancestor of HEAD and is not HEAD itself. `gates/git_discipline_gate.py` `check_push_reviewed` names it in the unreviewed deny, and `review/review_launch.py` `default_base` picks it for a bare launch on a clean tree, in place of its own walk of the record.

## Evidence

A converged review recorded a dirty tree at HEAD; the dirty change was then thrown away while an earlier commit on HEAD stayed unreviewed. The push gate denied, and a bare `/review` picked HEAD as the base and stopped with an empty scope, so the session had no path forward. The deny also named a base that a rebase had left off the branch.

## Result

`test_a_bare_launch_skips_a_recorded_base_that_is_head_itself_for_an_older_one` fails before the change (the launch stops with an empty scope) and passes after. `test_git_discipline_gate.py` `test_newest_reviewable_base_is_the_newest_recorded_base_that_is_a_strict_ancestor_of_head` and `test_newest_reviewable_base_skips_a_recorded_base_that_is_no_ancestor_of_head` pin the gate's read.

## Watch

Read the next push deny's `base=` for a commit that is not on the branch.

## Back-out

Restore `latest_reviewed_base` in `lib/reviewed_tree.py` and the gate's call to it, and restore the walk of `shared_base_entries` in `review_launch.default_base`.
