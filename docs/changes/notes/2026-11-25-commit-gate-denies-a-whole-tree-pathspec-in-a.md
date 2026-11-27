---
type: "Change"
change_type: "fixed"
title: "Commit gate denies a whole-tree pathspec in a shared clone"
description: "The shared-clone commit rule treats a pathspec that names the whole tree as a bare commit, so a session cannot sweep its peers' staged files in with `-- .` or `-- :/`."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T10:23:52-06:00"}
seq: 1
kind: "fix"
components: ["script/git-discipline-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_git_discipline_gate.py::test_a_whole_tree_pathspec_in_a_listed_clone_is_denied"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`lib/commit_pathspec.py` `is_bare_commit` also returns True when a pathspec after `--` is `.`, `./`, `:/`, `:(top)` or `*`, even beside a named file. The gate rule needed no edit.

## Evidence

`git commit -m x -- .` and `-- :/` named the whole tree and passed the rule that requires a pathspec, so they committed peers' staged files.

## Result

The new gate test and six new rows in `test_commit_pathspec.py` failed before the fix (5 errors in the gate file, 6 failed rows) and pass after. No hook-time change: the check adds one regex match to a path already run.

## Watch

None. Read the next gate denies in a shared clone for false denies.

## Back-out

Remove `names_whole_tree` and its call from `lib/commit_pathspec.py`.

