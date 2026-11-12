---
type: "Change"
change_type: "fixed"
title: "refactor branch-prep covers uncommitted and untracked files"
description: "With no --head, /refactor branch-prep lists and sweeps the merge-base span against the work tree plus untracked files, and bounds the smell-reviewer to that span."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-11T23:45:51-06:00"}
seq: 14
kind: "fix"
components: ["skill/refactor", "script/refactor-flow", "script/script-utils"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_refactor_flow.py::RefactorFlowTest::test_branch_prep_covers_committed_uncommitted_and_untracked_files"
asked: ""
proof: []
unmeasured: ""
---

## Change

`refactor_flow.py branch-prep` with no `--head` diffs the merge base of the base and HEAD against the work tree
(`git diff <merge-base>`), adds untracked files (`git ls-files --others --exclude-standard`) labelled `untracked`
(`untracked, binary` for a non-text file), and sweeps each untracked text file's lines as added lines. The smell
bound names `git diff <merge-base>` plus the untracked files. The empty-diff stop fires only when committed,
uncommitted and untracked changes are all empty. With `--head` the behavior is unchanged. The untracked listing (`untracked_paths`) and the text read
(`read_text_lines`) now live in lib/script_utils.py, shared with `changed_files`.

## Evidence

judgment: uncommitted edits and untracked new files were missing from the smell-reviewer prompt, so a refactor run
over a work tree reviewed only the committed part.

## Result

The new work-tree test, the untracked-only test and the updated bound assertion fail on the old tree and pass; the
refactor flow test file passes (101 tests).

## Watch

None: the span is fixed by the git state.

## Back-out

Revert the commit.
