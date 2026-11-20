---
type: "Change"
change_type: "fixed"
title: "refactor_flow takes untracked files and keeps its log input in the git dir"
description: "refactor simplify-prep lists untracked files of its target, the branch log input defaults to the repo's git dir, and close-branch Step 5 names the log --mode branch command."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T12:55:21-06:00"}
seq: 8
kind: "fix"
components: ["script/refactor-flow", "script/simplify-slices", "skill/close-branch", "skill/refactor"]
evidence: ["refactor-simplify-prep-stops-on-untracked-files", "close-branch-refactor-flow-file-in-tmp-is-gone-by"]
watches: []
test: "tests/scripts/test_refactor_flow.py::RefactorFlowTest::test_simplify_prep_on_only_untracked_files_does_not_stop"
asked: ""
proof: []
unmeasured: ""
---

## Change

`refactor_flow.py` lists target files with `git ls-files --cached --others --exclude-standard` (`untracked_files`, `ls_files`). `fresh_log_input()` with no `REFACTOR_LOG_INPUT_DIR` writes under `git rev-parse --git-path refactor-flow`. close-branch Step 5.3 runs `refactor_flow.py log --mode branch` and points at escape-ratchet.md.

## Evidence

simplify-prep printed STOP on a target of only untracked files. The branch log input under the system temp folder was gone by the time close-branch logged.

## Result

New tests in `test_refactor_flow.py`: tracked and untracked files listed, no STOP on untracked-only, log input under the git dir, close-branch names the command.

## Watch

None.

## Back-out

Revert the commit.
