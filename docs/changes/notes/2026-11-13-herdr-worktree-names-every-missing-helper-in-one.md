---
type: "Change"
change_type: "fixed"
title: "herdr-worktree names every missing helper in one error with the stow command"
description: "herdr-worktree --fork collects every helper missing from the bin folder and names them all in one error, with the exact stow command, instead of stopping at the first."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-13T13:00:00-06:00"}
seq: 3
kind: "fix"
components: ["script/herdr-worktree"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_herdr_worktree.py::HerdrWorktreeTest::test_a_fork_with_both_helpers_missing_names_both_and_the_stow_command_for_the_real_checkout"
asked: ""
proof: []
unmeasured: ""
---

## Change

`scripts/.local/bin/herdr-worktree`: the `--fork` helper check collects every missing helper (`detach`,
`herdr-worktree-watch`) and prints one error naming each, with `stow -d <dotfiles> -t "$HOME" -R scripts` for the
checkout that holds the script's real file. It still exits 1 before anything is created.

## Evidence

judgment: a session hit `detach` missing, linked it, reran, then hit `herdr-worktree-watch` missing; it could not run
stow itself, so the fork never started until the user stepped in.

## Result

The new test fails on the old tree and passes; the full suite passed (3779 tests, 0 failed).

## Watch

None: a fixed error message.

## Back-out

Revert the commit.
