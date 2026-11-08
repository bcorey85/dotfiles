---
type: "Change"
change_type: "fixed"
title: "pull_keep_index re-apply rebuilds built pages and keeps the staged split on a conflict"
description: "The re-apply names its stash commit to the built-page driver, and a conflicting re-apply gives every other file back its staged or unstaged state and prints the conflicted paths and the command that resolves them."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T10:20:11-06:00"}
seq: 4
kind: "fix"
components: ["script/pull-keep-index"]
evidence: ["pull-keep-index-re-apply-bypasses-the-built-page"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::test_a_conflicting_re_apply_keeps_the_staged_and_unstaged_split"
asked: ""
proof: []
unmeasured: ""
---

## Change

`claude/.claude/scripts/tools/pull_keep_index.py`:

- `git stash apply --index` runs with `BUILT_PAGE_STASH=<saved commit>`, the variable the agent-evals driver reads.
- When the apply leaves conflicted paths, the script builds the tree the index would have held (HEAD plus the saved staged changes, in a scratch index). It then resets every applied path to that tree, so unstaged files are unstaged again and staged ones stay staged. Conflicted paths stay conflicted.
- It exits 1 and names the conflicted paths, plus `git -C <repo> reset -q <tree> -- <paths>`, which marks them resolved with their staged text once the markers are fixed.

## Evidence

2026-11-08, ~/agent-evals: the re-apply left QUEUE.md conflicted and staged two queue files that had been unstaged. Another session then committed the conflict markers at 3ceca80c.

## Result

Both new tests failed before the change: the conflicted apply left `M  k` and `M  m` staged, and the driver saw no stash. Both pass after it, and `test_pull_keep_index.py` passes 7 of 7.

## Watch

None: the tests cover it.

## Back-out

Revert the change to `pull_keep_index.py`. Pulls then fall back to the text merge and the lost split.
