---
type: "Change"
change_type: "added"
title: "Review loop feeds the smell reviewer each added function's nearest other functions"
description: "The review loop's first smell review now gets, for each added function, its nearest other functions in the repo, so a private helper that repeats an exported one under another name reaches the reviewer as a candidate pair."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T20:22:50-06:00"}
seq: 3
kind: "fix"
components: ["script/review-loop", "agent/smell-reviewer", "script/refactor-flow"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_nearest.py::ReviewLoopNearestTest::test_the_smell_prompt_names_the_exported_helper_a_new_private_helper_resembles"
asked: ""
proof: []
unmeasured: "The smell-reviewer text now names the first review-loop round as a source of the candidate catalog. This widens who hands the catalog over and adds no rule; it has no rule-meter arms."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

The review loop's first smell review gets the nearest-other-functions catalog that /refactor branch-prep already builds, limited to the files the smell reviewer owns. `shape_clones.catalog_shapes` is a catalog-only step (changed and added functions, then listings, uncataloged count and notes) that `branch_shapes` also uses, so the review loop never runs the pair search. One renderer (`shape_clones.catalog_lines`, which takes the heading) and one diff argument list (`lib/source_text.py` `DIFF_COMMAND_ARGS`) serve both callers. The untracked-file listing moved from the refactor flow to `lib/untracked_listing.py`, which reads each file's kind through `lib/change_added_ranges.py` `read_untracked` and raises the caller's error type; `refactor_flow` and `simplify_flow` call it with no wrapper left behind, so the new `review/review_loop_nearest.py` imports only lib modules and `shape_clones`. A repo whose files git cannot list gives a skipped result, and the block reads as not read.

## Evidence

A branch added private bracket-matching and split helpers while a shared module already exported the same jobs under other names. The review loop passed it, and three later simplify passes found it one at a time. The clone-pair feed fires only on same-shape bodies, and the review loop's smell prompt had no catalog.

## Result

A replay of a diff that adds a private helper resembling an exported one, under a different name and return shape, puts the pair in the smell-reviewer prompt. Before the change, the prompt named no candidate. Full suite: 6677 tests, 0 failed.

## Watch

None. No intake number reads the smell reviewer's prior-art catches per round.

## Back-out

Revert the branch commit.
