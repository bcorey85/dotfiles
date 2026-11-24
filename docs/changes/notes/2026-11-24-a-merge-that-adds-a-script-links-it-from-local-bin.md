---
type: "Change"
change_type: "added"
title: "a merge that adds a script links it from ~/.local/bin"
description: "A post-merge hook restows the scripts package when a merge in the stowed main checkout leaves a script unlinked."
generated: {"by": "claude-opus-5-5/main", "at": "2026-11-24T12:36:09-06:00"}
seq: 5
kind: "fix"
components: ["script/post-merge"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_post_merge_hook.py::PostMergeHookTest::test_a_merge_that_adds_a_script_links_it"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`.githooks/post-merge` runs after a merge in the main worktree whose checkout `~/.local/bin` already links into. When
`install/check-script-links` reports a gap, it runs `stow -R -t $HOME scripts` and prints the check's new result. A
linked worktree, a checkout that `~/.local/bin` does not link to, and a merge with no gap restow nothing. A stow failure
or a missing stow prints one message and the merge still succeeds. The CI workflow installs stow so the hook tests run.

## Evidence

Judgment: the tests run real `git merge` (fast-forward and merge commit) and real stow in a temporary home.

## Result

A script added by a merge is linked from `~/.local/bin` without a manual `install/stow`.

## Watch

None: `install/check-script-links` shows a gap after any merge that skipped the hook.

## Back-out

Delete `.githooks/post-merge` and `tests/scripts/test_post_merge_hook.py`; the stow line in the workflow can stay.
