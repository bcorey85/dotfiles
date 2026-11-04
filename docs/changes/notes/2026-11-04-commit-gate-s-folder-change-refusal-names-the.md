---
type: "Change"
change_type: "fixed"
title: "Commit gate's folder-change refusal names the plain commit for notes-only commits"
description: "A cd commit of staged notes files is told to run a plain commit from the repo root, so one notes commit meets one refusal in place of two."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-04T00:18:04-06:00"}
seq: 1
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_cd_commit_of_staged_notes_names_the_plain_commit_not_git_c"
asked: ""
proof: []
unmeasured: "The deny text is read by no intake number."
---

## Change

- `claude/.claude/scripts/review/review_commit_gate.py`: when the gate cannot place a command in a repo and every staged file in a credited repo is a notes path, the refusal says to run a plain `git commit` from the repo root, not the `git -C <repo> commit` form.
- The notes check reuses the gate's existing matching: the tail of `ships_only_notes` moved into `all_notes_paths`, which both it and the new `staged_files_are_notes` call.

## Evidence

A `cd <repo> && git commit` was refused with a pointer to `git -C`; the `git -C` commit of notes was then refused with a message saying a notes-only commit must be a plain `git commit`. Two blocks for one commit.

## Result

The named test fails with the new branch disabled and passes with it. Other denies are unchanged.

## Watch

None. No intake number reads the deny text.

## Back-out

Revert the commit. The refusal names the `git -C` form again.
