---
type: "Change"
change_type: "fixed"
title: "herdr-worktree names a forked session for its worktree"
description: "herdr-dev launches a forked Claude session with --name set to the worktree folder, so a fork no longer shows up to peers under its parent's session name."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T11:13:39-05:00"}
seq: 317
kind: "fix"
components: ["script/herdr-dev", "script/herdr-worktree"]
evidence: ["queue item: herdr-worktree fork keeps the parent's session name"]
watches: []
test: "tests/scripts/test_herdr_worktree.py::HerdrDevTest::test_a_forked_session_is_named_for_its_worktree_not_its_parent"
asked: ""
proof: []
unmeasured: ""
---

## Change

`herdr-dev` adds `--name <worktree folder>` to the `claude --resume <id> --fork-session` command it types into the claude pane. The folder name is shell-quoted. A fresh, unforked claude pane is unchanged.

## Evidence

In an orchestrated run, a slice session forked by `herdr-worktree --fork` sent messages signed with the orchestrator's own name. Only the socket address told the two sessions apart.

## Result

The new test fails without the change and passes with it. The other herdr-worktree and herdr-dev tests still pass.

## Watch

—

## Back-out

Drop the `--name` argument from the fork command in `herdr-dev`.
