---
type: "Change"
change_type: "fixed"
title: "A quoted path:line later in a finding is not its location"
description: "parse_finding takes the first path a finding names as its location and skips a path:line inside a quoted span."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T13:35:57-06:00"}
seq: 22
kind: "fix"
components: ["script/finding-record", "script/script-utils"]
evidence: ["review-loop-takes-a-quoted-fixture-path-as-a"]
watches: []
test: "tests/scripts/test_review_loop_findings.py::DottedSymbolIsNotALocationTest::test_a_bare_path_with_any_extension_or_case_is_a_location_with_line_zero"
asked: ""
proof: []
unmeasured: ""
---

## Change

`finding_record.parse_finding` reads the location as the first path the text names. A `path:line` inside quotes or a longer backtick span is skipped. A bare path with a folder before any `path:line` is the location, with line 0.

## Evidence

A reviewer finding named a test file, then quoted a fixture string holding `a.py:1`. The loop took `a.py:1` as the location and skipped the finding as not in the tree.

## Result

FindingLocationTest and DottedSymbolIsNotALocationTest in `test_review_loop_findings.py`.

## Watch

None.

## Back-out

Revert the commit.
