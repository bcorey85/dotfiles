---
type: "Change"
title: "A plain bullet under Automated Verification is read as an open check"
description: "A top-level list item under `#### Automated Verification` that is not a checkbox is read as an open `- [ ]` item, and plan check prints a file:line warning for it, instead of the item being skipped unrun."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T03:00:00-05:00"}
seq: 144
kind: "fix"
components: ["script/plan-format", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_plan_format.py::AutomatedVerificationRowsTest::test_a_plain_list_item_under_automated_verification_is_read_as_an_open_box"
asked: "2026-10-28: agent-evals-64 assigned queue item plan-format-drops-plain-bullets-under-automated, and ruled that the item is read as a check, not a failure"
proof: []
unmeasured: ""
---

## Change

- `plan_format.verification_list_items` walks the Automated Verification list and returns every top-level list
  item (`-`, `*`, `+`, `1.`, `1)`), checkbox or not. Indented lines stay out.
- `plan_format.automated_verification_rows` returns a non-checkbox item as `- [ ] <text>`, so every reader runs it
  like an open box. `- N/A — <reason>` and `- N/A: ...` read as N/A items.
- `plan_format.plain_verification_item_warnings` gives one `name:line: warning:` row per such item, with the form
  `- [ ] <check>`. `plan check` prints the rows and does not fail on them.

## Evidence

- A plain `- \`cmd\`` bullet under the heading was neither run nor flagged.
- The new test_plan_format.py and test_code_step.py tests fail on the old scripts.
- Over the 743 real `~/dev/*/docs/plans/*/spec.md` files, 186 get a warning. The write-time check stopped 80
  before and stops 98 now. The 18 new stops are copies of two plans, LED-30 and LED-13-guard-migration, whose open
  phase holds a note bullet with no backticked command, which a box with the same text also fails.

## Result

- A plain bullet under Automated Verification is run, or flagged like a box, and never silently dropped.

## Watch

—

## Back-out

Revert the commit.
