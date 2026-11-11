---
type: "Change"
change_type: "fixed"
title: "pull_keep_index pull_target docstring names every exit"
description: "The pull_target docstring again names the exit 1 with the git error when the origin lookup fails on a branch with no upstream."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T22:24:04-06:00"}
seq: 7
kind: "fix"
components: ["script/pull-keep-index"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::PullKeepIndexTest::test_a_branch_with_no_upstream_and_no_origin_exits_1_with_the_git_error"
asked: ""
proof: []
unmeasured: ""
---

## Change

`scripts/tools/pull_keep_index.py` `pull_target` docstring lists the origin lookup failure exit (no upstream set)
beside the configured-upstream and branch-name exits. Docstring only; no behavior change.

## Evidence

judgment: the review of the prior commit found the docstring rewrite dropped that exit.

## Result

The docstring matches the three exits the code has; the existing test covers the origin lookup failure.

## Watch

None: docstring only.

## Back-out

Revert the commit.
