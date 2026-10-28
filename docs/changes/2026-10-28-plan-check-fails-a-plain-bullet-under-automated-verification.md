---
type: "Change"
title: "Plan check fails a plain bullet under Automated Verification"
description: "A top-level list item under `#### Automated Verification` that is not a checkbox fails the strict read with its file, line and the checkbox form, instead of being skipped unrun."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T03:00:00-05:00"}
seq: 144
kind: "fix"
components: ["script/plan-format", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_plan_format.py::AutomatedVerificationRowsTest::test_a_plain_list_item_under_automated_verification_raises_with_its_file_line_and_the_checkbox_form"
asked: "2026-10-28: agent-evals-64 assigned queue item plan-format-drops-plain-bullets-under-automated"
proof: []
unmeasured: ""
---

## Change

- `plan_format.automated_verification_rows`: under `strict`, a top-level list item (`-`, `*`, `+`, `1.`, `1)`)
  inside the Automated Verification list that is not `- [ ]` or `- [x]` raises PlanFormatError with
  `name:line:`, the item, and the form `- [ ] <check>` (or `- [ ] N/A — <reason>`). Indented lines stay allowed.
  Non-strict reads still skip the item.
- The plan-hook write check, `plan check` and `code-step start` read the list strictly, so each one fails on it.

## Evidence

- A plain `- \`cmd\`` bullet under the heading was neither run nor flagged.
- The new test_plan_format.py and test_code_step.py tests fail on the old script.
- Over the real plans, 186 of 743 `~/dev/*/docs/plans/*/spec.md` files hold such an item: N/A bullets, note
  bullets and backticked command bullets.

## Result

- A plain bullet under Automated Verification fails at write time, so it is never silently dropped.

## Watch

—

## Back-out

Revert the commit.
