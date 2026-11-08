---
type: "Change"
change_type: "fixed"
title: "pull_keep_index stops before touching a tree inside a stopped rebase"
description: "A run that starts inside a stopped rebase now exits 1 with the tree and index untouched, where it used to reset the tree hard and lose the local edits; every stop names the branch, the conflicted paths and both ways out."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T13:36:32-06:00"}
seq: 6
kind: "fix"
components: ["script/pull-keep-index"]
evidence: ["session report"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::test_a_run_inside_a_stopped_rebase_touches_nothing_and_names_the_way_out"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `tools/pull_keep_index.py`: before it sets anything aside, a run that finds `rebase-merge` or `rebase-apply` exits 1 and changes nothing.
- When the pull itself stops mid-rebase, the message names the rebased branch, the conflicted paths ("no conflicted paths" when the stop has none), `rebase --continue` and `rebase --abort`, and then the saved-stash line to run after.
- Two tests: a run inside a stopped `edit` rebase leaves the staged and unstaged files as they were, and a pull that stops on a conflicting local commit names the path and both ways out.

## Evidence

Session report, 2026-11-08, agent-evals: a run inside a stopped rebase reset the tree hard, so two local queue edits were lost. Later commits landed on the detached HEAD, and a built page was committed with conflict markers. The new test fails before the fix: the tree comes back empty.

## Result

`test_pull_keep_index.py`: 9 tests pass, 2 of them new, and both fail before the fix.

## Watch

None: a fix with a test.

## Back-out

Revert the commit.
