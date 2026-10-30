---
type: "Change"
change_type: "fixed"
title: "The commit gate names the command form that cost a reviewed commit its credit"
description: "When a converged review covers the repo but the commit command holds a cd, pushd, eval, source, ., git dir option or $, the review commit gate's denial names that form and says not to run /review again."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T12:02:10-05:00"}
seq: 319
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["queue item: commit gate denial hides that a folder change cost the review credit"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_folder_change_or_substitution_in_a_reviewed_repo_is_denied_naming_that_form"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review_commit_gate.py` reads the part of a commit command that loses review credit through one function, `credit_losing_form`. When every repo the commit runs in has credit and only that form lost it, the denial names the form, tells the session not to run /review again, and gives the plain `git commit` or `git -C <repo> commit` form. Any other denial keeps the old text.

The `stale` checks in `test_code_step_resume.py` now match the word only outside a path, so a checkout folder or `stale_prose.py` in the output no longer fails them.

## Evidence

A session with a converged review had a `cd <repo> && git commit` denied with "no converged /review". Nothing in the denial said the `cd` caused it, so the session could not tell. Five resume tests failed when they were run from a checkout path that holds the word stale.

## Result

The new gate test fails on the old gate and passes on the new one, and the gate suite passes. The resume suite failed 5 tests when run from a copy of the scripts under a `stale-checkout` folder, and passes 120 of 120 from both paths after the change.

## Watch

—

## Back-out

Drop the form-naming branch in `check_commit`. Every denial then goes back to the "no converged /review" text.
