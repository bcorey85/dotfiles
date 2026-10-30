---
type: "Change"
change_type: "fixed"
title: "A coder's lint runs the same complexity gate as the full suite"
description: "A coder's lint of its changed files now fails on a function past complexity 10 in the code-step and review-flow files, as the full suite does, so the failure shows before review instead of costing a review iteration."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T08:57:39-05:00"}
seq: 338
kind: "fix"
components: ["script/run-sh"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_lint_script.py::LintScriptTest::test_a_gated_file_past_the_complexity_limit_fails_the_lint_of_that_file"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `tests/lint.sh` holds the whole lint of the suite: the ruff rules pass, the report-only complexity pass, and
  the complexity gate on the code-step and review-flow file lists. With no arguments it lints as `tests/run.sh` did.
  With `.py` file arguments it runs `ruff check` on them and the complexity gate on those among them that are in the
  two gated lists; other arguments are skipped, except review/verify-log and review/verify-prep, which have no .py suffix.
- `docs/toolkit-script-rules.md` tells a coder to run `bash tests/lint.sh <changed .py files>` before hand-over, in
  place of a plain `ruff check`.
- `tests/run.sh` calls `tests/lint.sh` in place of its own lint block. A missing ruff still stops the run at once
  with the same message, and a failed lint still ends the run on `FAILED: lint`.

## Evidence

judgment: a function past complexity 10 passed the coder's targeted `ruff check` on its changed files, then failed
the full suite at the end of review and cost a review iteration. The targeted check never ran the gate on the two
file lists.

## Result

The named test fails before (no `tests/lint.sh`) and passes after: a gated file with a function of complexity 12 fails
`bash tests/lint.sh <file>`.
`test_the_same_function_in_a_file_outside_the_gated_lists_passes` shows the same function in a non-gated path passes.

## Watch

None.

## Back-out

Move the lint block of `tests/lint.sh` back into `tests/run.sh` in place of the `lint.sh` call, and delete
`tests/lint.sh` and `tests/scripts/test_lint_script.py`.
