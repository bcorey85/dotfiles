---
type: "Change"
change_type: "fixed"
title: "built-page driver rebuilds pages during a stash apply named by BUILT_PAGE_STASH"
description: "agent-evals `bin/merge_built_page.py` treats the stash commit named in BUILT_PAGE_STASH like an autostash, so the re-apply in pull_keep_index.py rebuilds QUEUE.md in place of a text merge."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T10:20:11-06:00"}
seq: 5
kind: "fix"
components: ["script/merge-built-page"]
evidence: ["pull-keep-index-re-apply-bypasses-the-built-page"]
watches: []
test: "bin/test_merge_built_page.py::test_a_named_stash_apply_with_dirty_pages_ends_clean"
asked: ""
proof: []
unmeasured: ""
---

## Change

agent-evals `bin/merge_built_page.py`: `autostash_commit` reads the stash commit from the `BUILT_PAGE_STASH` variable first, then from `rebase-merge/autostash` or `MERGE_AUTOSTASH`. A `git stash apply` run with that variable set gets the same rebuild, untracked-source copy included, as the apply at the end of `pull --autostash`. Two tests in `bin/test_merge_built_page.py` run the stash-create, pull, stash-apply sequence.

## Evidence

2026-11-08, ~/agent-evals: the re-apply in pull_keep_index.py merged QUEUE.md as text ("no rebase pick or one-head merge in progress") and left it conflicted. Conflict markers were committed at 3ceca80c.

## Result

Both new tests failed before the change with the same driver line as the field run, and pass after it. The agent-evals test file passes 30 of 30.

## Watch

None: the tests cover it.

## Back-out

Drop the `BUILT_PAGE_STASH` read from `autostash_commit`.
