---
type: "Change"
change_type: "fixed"
title: "Quality-check cap lets a scoped cargo test run"
description: "The quality-check cap no longer denies a repeat of a cargo test scoped to a named lib, doc, test target, bin or filter; the unscoped run stays capped."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T23:30:54-05:00"}
seq: 31
kind: "fix"
components: ["script/quality-check-cap"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_quality_check_cap.py::QualityCheckCapTest::test_a_cargo_test_scoped_to_a_named_target_is_never_a_repeat"
asked: ""
proof: []
unmeasured: "A scoped run is not logged separately; no intake number reads it."
---

## Change

A `cargo test` with `--lib`, `--doc`, `--test/--bin/--example/--bench <name>` or a test-name filter is skipped by the cap. Unscoped, `--workspace`, `--all-targets` or package-only runs stay capped. A read-only `cargo fmt --check` was already uncapped. Other runners are unchanged.

## Evidence

A coder on a Rust repo was denied scoped runs the rule tells it to make.

## Result

Scoped cargo runs and fmt checks pass the cap; the unscoped run is still denied.

## Watch

None.

## Back-out

Revert the commit.

