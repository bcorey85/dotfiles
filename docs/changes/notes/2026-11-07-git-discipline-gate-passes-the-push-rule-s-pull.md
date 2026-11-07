---
type: "Change"
change_type: "fixed"
title: "git-discipline-gate passes the push rule's pull"
description: "`git -C <repo> pull --rebase=merges --autostash && git -C <repo> push`, the form the global push rule names, passes the gate."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-07T01:28:20-06:00"}
seq: 3
kind: "fix"
components: ["script/git-discipline-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_git_discipline_gate.py::GitDisciplineGateTest::test_autostash_pull_right_before_a_push_in_the_same_directory_passes"
asked: ""
proof: []
unmeasured: ""
---

## Change

A `pull --autostash` passes only when `&&` joins it to a push that opens the next step with the same `-C` text and no repo-selecting option or env. A lone pull, `||` or `;`, a different directory, `rebase`/`merge --autostash` and the autostash config stay denied. The replay corpus gains `gdg-pull-autostash-before-push`; `gdg-pull-autostash` stays a deny.

## Evidence

judgment: every push that followed the global rule was blocked once, then redone with --no-autostash. The new test fails on the base commit and passes after.

## Result

Median run time over 21 runs: git_discipline_gate 34 ms against a bare Python start of 8 ms.

## Watch

—

## Back-out

Revert the commit's hunks in the named files.

