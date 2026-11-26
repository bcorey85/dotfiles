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

The review loop's first smell review gets the nearest-other-functions catalog that /refactor branch-prep already builds, limited to the files the smell reviewer owns. One renderer (`shape_clones.catalog_lines`) and one diff flag list (`lib/source_text.py` `DIFF_FLAGS`) serve both callers. The new `review/review_loop_nearest.py` builds the block. A repo whose files git cannot list now reads as not read (`ShapeResult.repo_unread`), not partly read.

## Evidence

A branch added private bracket-matching and split helpers while a shared module already exported the same jobs under other names. The review loop passed it, and three later simplify passes found it one at a time. The clone-pair feed fires only on same-shape bodies, and the review loop's smell prompt had no catalog.

## Result

A replay of a diff that adds a private helper resembling an exported one, under a different name and return shape, puts the pair in the smell-reviewer prompt. Before the change, the prompt named no candidate. Full suite: 6675 tests, 0 failed.

## Watch

None. No intake number reads the smell reviewer's prior-art catches per round.

## Back-out

Revert the branch commit. The refactor branch-prep output is unchanged in content.
