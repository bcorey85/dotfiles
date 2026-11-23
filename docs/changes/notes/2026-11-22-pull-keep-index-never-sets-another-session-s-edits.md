---
type: "Change"
change_type: "fixed"
title: "pull_keep_index never sets another session's edits aside in a shared checkout"
description: "When another live session works in the same repo and tracked changes exist, pull_keep_index no longer sets them aside: it fetches into a named ref and fast-forwards in place, or refuses naming the dirty files and the way out. Every run, --put-back included, takes a per-repo lock."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T18:20:08-06:00"}
seq: 27
kind: "fix"
components: ["script/pull-keep-index"]
evidence: ["tests"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::PullKeepIndexTest::test_a_shared_pull_keeps_the_other_sessions_edit_in_the_tree_for_the_whole_pull"
asked: ""
proof: []
unmeasured: "No count shows how often two live sessions shared one checkout with tracked changes during a pull."
---

## Change

When another live session works in the same repo and tracked changes exist, pull_keep_index no longer sets those changes aside. It fetches into a named ref and fast-forwards in place, so the edits stay in the tree for the whole pull. When the pull would overwrite a dirty file, or the branch has diverged, it refuses before it changes anything. The message names the dirty files and the way out, and states that nothing was set aside. A clean tree with another session, and a run with only the caller's own session, keep the usual route.

Every run, `--put-back` included, takes a per-repo lock first and waits up to `PULL_KEEP_INDEX_LOCK_SECONDS` (a positive integer, default 300). When the wait ends, it exits 1.

## Evidence

The pull_keep_index tests cover the shared route. One checks that the other session's edit is in the tree at every branch-ref write and that no named ref is left. Others cover a refusal on an overwritten dirty file, a refusal on a diverged branch, a clean shared tree, a row with the caller's own session id, a pull with nothing new, a detached head, a failed fetch, a failed merge and a first pull that sets the upstream.

## Result

The pull_keep_index tests pass.

## Watch

A refusal on a shared checkout where the dirty files would not have clashed, or a run that waits out the full lock time because another run holds the lock.

## Back-out

Revert `pull_keep_index.py` and its tests to the route that sets tracked changes aside whether or not another session is live.
