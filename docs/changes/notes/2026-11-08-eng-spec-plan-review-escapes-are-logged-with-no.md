---
type: "Change"
change_type: "fixed"
title: "eng-spec plan-review escapes are logged with no miss_reason"
description: "eng-spec step 20b no longer passes miss_reason=plan-gap, and log-escape takes a gate_missed=eng-spec row without it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T23:59:00-06:00"}
seq: 15
kind: "fix"
components: ["skill/eng-spec", "script/log-escape"]
evidence: ["log-escape-drops-miss-reason-that-eng-spec-6b"]
watches: []
test: "tests/scripts/test_log_escape.py::test_an_eng_spec_escape_needs_no_miss_reason_and_sends_none"
asked: ""
proof: []
unmeasured: ""
---

## Change

Step 20b of `eng-spec/phases/6b-review.md` drops `miss_reason=plan-gap` from its log-escape line. log-escape still requires miss_reason on every other row. A `gate_missed=eng-spec` row may leave it out, and is then sent without the field.

## Evidence

log-escape-drops-miss-reason-that-eng-spec-6b

## Result

A plan-review row no longer trips the "this ledger build does not store miss_reason" note. The field held nothing new: gate_missed=eng-spec already means plan-gap, and escape_miss_reasons counts only gate_missed=review rows. Keeping the field in the local file instead would not reach that reader, which reads the ledger first, and would split each row between two stores.

## Watch

—

## Back-out

Revert the commit.
