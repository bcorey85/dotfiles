---
type: "Change"
change_type: "fixed"
title: "pull_keep_index rebuilds staged built pages on the put-back and prints a gate-allowed recovery"
description: "When the staged local changes clash with the pull only on built pages, pull_keep_index re-applies without the index so the merge driver rebuilds them, keeps the staged split and stages the rebuilt pages, but only when the repo configures the built-page merge driver; every failed put-back that leaves the changes unapplied names the script's own --put-back verb, which git-discipline-gate allows."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T09:26:30-06:00"}
seq: 1
kind: "fix"
components: ["script/pull-keep-index"]
evidence: ["queue item pull-keep-index-strands-local-edits-where-the-git: on 2026-11-21 a pull in ~/agent-evals with staged QUEUE.md and queue/index.md edits failed `stash apply --index` with 'conflicts in index' and no conflicted paths; the printed recovery was a stash apply, which the gate blocks, so the user had to restore the edits"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::PullKeepIndexTest::test_a_staged_clash_only_on_built_pages_is_rebuilt_and_the_split_kept"
asked: ""
proof: []
unmeasured: ""
---

## Change

When the re-apply with the index fails, `put_back` checks the paths that both the staged changes and the pull touched. When every one has `merge=built-page` and `git config --get merge.built-page.driver` succeeds in the repo (git text-merges a page whose driver is not configured), it applies the saved commit with no index (so the driver named by `BUILT_PAGE_STASH` rebuilds the pages). It then puts back each other file's staged state and runs `git add` on the rebuilt pages. Every failed put-back that leaves the changes unapplied now prints `python3 <script> --put-back <saved> <repo>` in place of a stash apply. The printed git commands quote every word, and those that name paths use `--literal-pathspecs`. `escaped_glob` is new in `lib/script_utils.py`. A `--put-back` call whose commit has no second parent, or whose repo has tracked changes, exits 1 with the usage.

## Evidence

A scratch reproduction of the 2026-11-21 run (a staged page that the pull also changed) exits 1 with "conflicts in index" on master. `test_a_staged_clash_only_on_built_pages_is_rebuilt_and_the_split_kept` fails without the change. Other new tests cover a clash that also hits an ordinary file (stops with `--put-back`), the `--put-back` verb, a driver that gives up, and a failed staging of the rebuilt pages.

## Result

The pull_keep_index tests and the full suite pass.

## Watch

A put-back that stages a rebuilt page the user had left unstaged, or a `--put-back` run that a gate blocks.

## Back-out

Revert `pull_keep_index.py` to apply with `--index` only and print the stash apply recovery.
