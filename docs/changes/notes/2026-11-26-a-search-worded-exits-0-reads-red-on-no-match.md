---
type: "Change"
change_type: "fixed"
title: "A search worded exits 0 reads RED on no match"
description: "An rg, grep or git grep criterion whose text says it exits 0 now reads as a presence check, so no match (exit 1) reads RED, not GREEN; ban wording on the same line still wins."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T03:52:39-06:00"}
seq: 5
kind: "fix"
components: ["script/criteria-dry-run", "shared/criteria-verdict"]
evidence: ["tests/scripts/test_criteria_verdict.py"]
watches: []
test: "tests/scripts/test_criteria_verdict.py::ItemVerdictTest.test_a_search_worded_exits_zero_reads_red_on_no_match_and_a_ban_still_reads_green"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`criteria_verdict.PRESENCE_WORDING` takes `exit(s) 0` and `exit code 0`.

## Evidence

A bench plan's `` `rg -q A f && rg -q B g` exits 0. `` items printed `GREEN rc=1` in the dry run: the line held no presence word, so it read as a ban. Six such lines across the bench runs. The test fails on the old tree (GREEN) and passes after (RED).

## Result

A presence criterion that does not hold yet reads RED before the work starts.

## Watch

—

## Back-out

Drop the `exit 0` branch from `PRESENCE_WORDING` and the new test.
