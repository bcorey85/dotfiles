---
type: "Change"
change_type: "fixed"
title: "a bare review on a clean tree reviews the commits since the last reviewed base"
description: "A bare /review on a clean work tree now reviews the commits since the last reviewed base (the HEAD when a converged review recorded it, so that review's own committed changes are included), or a merge HEAD's own changes, in place of stopping with nothing to review."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T06:33:08-06:00"}
seq: 11
kind: "fix"
components: ["script/review-launch"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_launch.py::ReviewLaunchTest::test_a_bare_launch_on_a_clean_merge_head_reviews_only_what_the_merge_itself_changed"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`review/review_launch.py` gains `default_base` and `clean_tree_base`. A launch with no `--base`, `--file`, `--fix`, `--also-fix` or findings on a work tree with no change in scope (plan-folder and `--ruled-out` files do not count) picks a base: the newest base in the shared reviewed-bases record (`reviewed_tree.shared_base_entries`) that is an ancestor of HEAD, when `push_review_state` says HEAD changed since the review, else the first parent of a HEAD merge commit. It prints the base and why, then goes on as a `--base` launch, so `merge_free_base` still folds merged-in commits out. A HEAD that is already reviewed, or a plain commit with no reviewed base, picks nothing and stops as before. `handoff_text` takes a `base` parameter: a launch with `--base`, typed or picked, and no `--handoff`, `--file` or findings to fix hands off "Review every change since {base}, commits included; what merge commits brought in is folded into that base."

## Evidence

The push gate denied a push as unreviewed and named `/review base=<ref>`; a bare `/review` on the committed, clean tree stopped with "nothing to review", so the session had no path from the deny to a review.

## Result

`test_a_bare_launch_on_a_clean_merge_head_reviews_only_what_the_merge_itself_changed` and `test_a_bare_launch_on_a_clean_tree_reviews_the_commits_since_the_last_reviewed_base` fail before the change (the launch stops) and pass after.

## Watch

Read the next bare /review on a clean tree for a base that reviews more than the unreviewed commits.

## Back-out

Drop `default_base`, `clean_tree_base`, the `base` parameter of `handoff_text` with its `options.base` branch, the `reviewed_tree` import and the `if not (options.base or paths or findings or options.fix):` guard in `command_launch` together with its `options.base = clean_tree_base(repo, plan, ruled_out)` line.
