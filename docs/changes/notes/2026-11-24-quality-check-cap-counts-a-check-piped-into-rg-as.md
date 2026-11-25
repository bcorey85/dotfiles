---
type: "Change"
change_type: "fixed"
title: "quality check cap counts a check piped into rg as cut"
description: "A check whose output is piped into rg is recorded as cut, so one rerun redirected to a file is allowed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T04:30:58-06:00"}
seq: 1
kind: "fix"
components: ["script/quality-check-cap"]
evidence: ["incident"]
watches: []
test: "tests/scripts/test_quality_check_cap.py::QualityCheckCapTest::test_rg_cuts_the_output_too"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`OUTPUT_FILTER_START` lists `rg` beside tail, head and grep, and the deny text names rg.

## Evidence

A check piped into `rg '^(Ran|OK|FAILED)'` was not recorded as cut, so the rerun redirected to a file was denied.

## Result

A check piped into rg allows one rerun sent to a file; a second rerun with no redirect is still denied.

## Watch

A deny after an rg-piped check that names tail, head, grep or rg.

## Back-out

Remove `rg` from `OUTPUT_FILTER_START` and the deny text.
