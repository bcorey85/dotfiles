---
type: "Change"
change_type: "fixed"
title: "A memory-capped run with a quoted option value shares the plain run's key"
description: "A systemd-run prefix with a quoted option value is now cut off like an unquoted one, so the capped run and the plain run of the same check share one key."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-24T16:38:51-06:00"}
seq: 3
kind: "fix"
components: ["script/quality-check-cap"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_quality_check_cap.py::WithoutSystemdRunTest::test_a_single_quoted_option_value_shares_the_plain_key"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

The cap gate drops a leading `systemd-run <options>` from a step so a capped run and the plain run share a key. The cut
used a quote-blind word pattern and kept the whole step when a quoted value held a blank. It now cuts at the blank that
ends the last dropped word, found with the shared quote positions, so `-p 'MemoryMax=8G'` and `-p "Description=unit
tests"` are dropped like `-p MemoryMax=8G`.

## Evidence

Judgment from a code read of the cut against the shared shell quoting helpers.

## Result

Two tests pin it: a double-quoted value with a blank and a single-quoted value both reduce to the plain command.

## Watch

None: a test pins it.

## Back-out

`git revert` the commit.
