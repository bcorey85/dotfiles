---
type: "Change"
change_type: "fixed"
title: "Staged-claim check reads the work trees the session staged in"
description: "The Stop hook's staged-claim check passes a claim that names no absolute path when a work tree the session itself staged in, by git -C or cd, holds every named file that exists in the cwd checkout or in that tree (any staged file when none of the named paths exists), so a session that stages in a linked worktree is no longer refused."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T12:03:14-05:00"}
seq: 382
kind: "fix"
components: ["script/staged-claim-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_staged_claim_gate.py::StagedClaimGateTest::test_a_claim_passes_only_when_a_worktree_the_session_staged_in_holds_staged_files"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The check reads the session transcript for Bash commands that stage in a named work tree: `git -C <tree> add` or
  `cd <tree> && ... git add`.
- When a staged claim names no existing absolute path and the cwd checkout's index is empty, the claim passes if one
  of those trees holds every relative path the claim names that exists in the cwd checkout or in that tree, resolved
  against that tree (any staged file, when it names none). A sibling worktree that another session staged in does not
  count.
- A claim that names an existing absolute path still checks only that path's repo.

## Evidence

A session kept its cwd in the main checkout and staged queue files in a linked worktree with `git -C`. Its claim
that the files were staged was refused twice, because the check read only the main checkout's empty index.

## Result

The new test fails before the edit and passes after it; the other 30 tests in the file (31 in all) still pass.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit.
