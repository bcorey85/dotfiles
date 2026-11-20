---
type: "Change"
change_type: "fixed"
title: "the quality-check cap keys on the env prefix and skips runs that never started"
description: "The quality-check cap allows a rerun that adds, changes or drops a leading NAME=value prefix, and records no failed run whose tool could not start or that hit an environment fault with no runner summary."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T06:39:45-06:00"}
seq: 7
kind: "fix"
components: ["script/quality-check-cap"]
evidence: ["quality-check-cap-denies-a-rerun-after-an"]
watches: []
test: "tests/scripts/test_quality_check_cap.py::QualityCheckCapTest::test_a_rerun_that_adds_or_changes_a_leading_env_prefix_is_allowed"
asked: ""
proof: []
unmeasured: ""
---

## Change

`gates/quality_check_cap.py` keeps the leading env prefix in the command key, and does not record a failed run whose
output shows the tool could not start, or an import fault with no runner summary.

## Evidence

The cap denied the rerun that fixed the environment with an env prefix, because the failed first run had counted.

## Result

Eight new tests in `test_quality_check_cap.py`.

## Watch

None.

## Back-out

Revert the commit.
