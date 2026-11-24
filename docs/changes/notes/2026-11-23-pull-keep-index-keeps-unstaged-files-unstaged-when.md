---
type: "Change"
change_type: "fixed"
title: "pull_keep_index keeps unstaged files unstaged when a put-back conflicts with nothing staged"
description: "A put-back that conflicts on one file while nothing was staged now gives every other file back its unstaged state, so the next commit in a shared clone no longer sweeps up other sessions' edits."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-23T22:58:47-06:00"}
seq: 10
kind: "fix"
components: ["script/pull-keep-index"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::PullKeepIndexTest::test_a_conflicting_re_apply_with_nothing_staged_leaves_the_other_files_unstaged"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`staged_tree` builds the index the put-back should leave by applying the saved staged diff to HEAD. With nothing
staged that diff is empty, `git apply` exits 128 on empty input, and the run stopped with "the staged files could not be
told apart" before it reset any file, so every file the conflicted `git stash apply` had applied stayed staged. The
empty diff now skips the apply: the staged tree is HEAD's, and the split restore runs.

## Evidence

Judgment from two sightings in a shared clone: a pull before push with only other sessions' unstaged edits in the
tree left about 60 files staged beside one conflicted file.

## Result

The new test fails on the old script (every unstaged file came back staged) and passes now; the 85 tests of the file
pass.

## Watch

None: a test pins it.

## Back-out

`git revert` the commit.
