---
type: "Change"
change_type: "fixed"
title: "Plan check reads only a standalone upper-case AC<n> as a reference"
description: "AC_REFERENCE matches `AC` case-sensitively and counts `_` as a word character, so `test_ac1_x`, `foo_AC2` and `ac3-evidence.md` no longer fail plan check as unknown AC ids."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T04:00:00-05:00"}
seq: 150
kind: "fix"
components: ["script/plan-format"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_spec_ac_check.py::AcReferenceFailuresTest::test_a_backticked_snake_case_test_name_holding_ac_n_is_not_a_reference"
asked: "2026-10-28: agent-evals-64 assigned queue item plan-check-reads-ac-n-inside-a-snake-case-test"
proof: []
unmeasured: ""
---

## Change

- `plan_format.AC_REFERENCE`: `_` joins the excluded characters on both sides, and `AC` matches upper case only.
  `ticket` before it still matches in any case. `AC1`, `(AC1)` and `ticket AC1` read as before.

## Evidence

- A spec that listed `test_ac1_pass_fail_and_zero_calls` failed plan check with "AC1 is not an id".
- Over the 743 real `~/dev/*/docs/plans/*/spec.md` files (parsed 743 of 743), the AC check gave 8687 failures before
  and 7423 after, with no new ones. Every lower-case standalone `ac<n>` in them is a name (`ac3-evidence.md`,
  `/tmp/ac19-hook.sh`), never a reference.
- The new test_spec_ac_check.py tests fail on the old script.

## Result

- A snake_case test name or a lower-case file name that holds `ac<n>` passes plan check.

## Watch

—

## Back-out

Revert the commit.
