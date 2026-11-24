---
type: "Change"
change_type: "fixed"
title: "Full-check receipt survives a commit of plans or docs alone"
description: "A commit or edit that touches only notes paths (docs/ Markdown and the committed notes list) now leaves the full-check receipt valid, so the gates stop asking for a second full suite run after a plan update; a change to any other path still voids it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-23T15:26:30-06:00"}
seq: 9
kind: "fix"
components: ["script/full-check", "shared/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_full_check_receipt.py::ReceiptValidityTest::test_a_commit_or_edit_of_notes_paths_only_after_the_run_keeps_the_receipt"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`lib/full_check_receipt.py`: the finished row also stores `notes_base` (HEAD's commit, or the empty tree before the
first commit) and `notes_tree`, the tree's fingerprint against that base with the log and the notes paths left out.
A receipt is valid when the current tree, fingerprinted the same way against `notes_base`, equals `notes_tree`,
whatever HEAD names. Before, the receipt also required HEAD to be unchanged, so a commit of a plan alone voided it.
A row written before this change has no `notes_tree` and keeps the old same-HEAD rule.
`lib/reviewed_tree.py`: `work_tree_fingerprint` takes an optional `base` and `notes_entries`.

## Evidence

Judgment: a docs-only commit after a green full check made every receipt reader report "HEAD moved", which forced a
full suite rerun on an unchanged code tree.

## Result

`test_full_check_receipt.py`: the notes-only test and the pre-first-commit test fail before the fix and pass after;
the code-commit test still voids the receipt. The receipt file and six related files run 223 tests, all passing; ruff
is clean.

## Watch

None.

## Back-out

`git revert` the commit.
