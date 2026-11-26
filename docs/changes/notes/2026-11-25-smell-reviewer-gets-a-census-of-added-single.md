---
type: "Change"
change_type: "added"
title: "A census script lists added single-caller forwarders, unread fields and superseded helpers"
description: "A script lists the forwarders, unread record fields and superseded helpers that a branch adds to Python code, for a reviewer to judge."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T18:30:37-06:00"}
seq: 5
kind: "fix"
components: ["script/review-loop", "agent/smell-reviewer", "skill/refactor"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_single_caller_census.py::SingleCallerCensusTest.test_lists_one_entry_of_each_kind_on_the_branch_and_none_on_the_base"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`lib/single_caller_census.py` lists three kinds of dead weight that a branch adds to Python code: a one-statement forwarder with one caller, a record field that nothing reads, and a helper whose every caller also calls a newer helper with every argument it passes the older helper. `lib/changed_lines.py` holds the added-line sets that `clone_pairs.py` and `shape_clones.py` also read.

## Evidence

`tests/scripts/test_single_caller_census.py` builds real git repos and checks each kind, its negative cases, untracked files, renames and sha256 repos.

## Result

The census gives a reviewer a list of suspects, counted by name; the reviewer decides. No review run has measured it yet.

## Watch

—

## Back-out

Revert the commit.

