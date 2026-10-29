---
type: "Change"
title: "quality-check-cap counts a tree-rewriting git call as an edit"
description: "git merge, checkout, switch, reset, pull, rebase, restore, cherry-pick, revert, am, apply, clean, rm and mv now count as edits, like a writing formatter, so a check run after one is not denied as a repeat."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T21:30:00-05:00"}
seq: 200
kind: "fix"
components: ["script/quality-check-cap"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_quality_check_cap.py::QualityCheckCapTest::test_a_git_call_that_rewrites_the_tree_counts_as_an_edit"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `claude/.claude/scripts/gates/quality_check_cap.py`: `writes_files` also counts a git call whose subcommand, read by `shell_command.git_subcommand` past git's own options, is in `GIT_TREE_REWRITE_SUBCOMMANDS`: merge, checkout, switch, reset, pull, rebase, restore, cherry-pick, revert, am, apply, clean, rm or mv.
- A check after such a step in the same command passes, and the step's PostToolUse touches the edits mark, as a writing formatter does.
- Closes the queue item quality-check-cap-denies-a-lint-rerun-after-a-git.

## Evidence

- A lint run chained after `git merge --ff-only` that changed files was denied: the PreToolUse fires before the merge, so the tree fingerprint still matched the last run.

## Result

- The new test fails on the old gate (18 assertions, 17 of them subtests) and passes on the new one. All 109 cap tests pass.

## Watch

—

## Back-out

Revert the commit. A check chained after a tree-changing git call is denied again.
