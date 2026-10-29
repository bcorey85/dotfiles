---
type: "Change"
title: "The Automated Verification reader and skill-done evidence leave code_step_boundary"
description: "The Automated Verification reader moves to code_step_verification.py and the skill-done evidence to code_step_closing.py, so code_step_boundary.py drops from 1021 to 706 lines."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T14:11:00-05:00"}
seq: 270
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_module_size.py::CodeStepModuleSizeTest::test_code_step_boundary_is_under_the_module_line_cap"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code_step_verification.py` holds the reader of a phase's Automated Verification items: `WHOLE_SUITE`,
`COMMAND_START`, the never-a-check programs, `VERIFICATION_ITEM_SHAPE`, `verification_command`,
`verification_item_problem`, `verification_format_failure`, `deferred_verification_items` and
`run_verification_commands`. It imports only `code_step_core` of the code-step modules. `code_step_boundary.py`,
`code_step_hooks.py`, `code_step_gates.py`, `code_step_start.py`, `code_step.py` and `tools/criteria_dry_run.py`
import it.

`code_step_closing.py` now holds all of `skill-done`: the evidence request lines, `record_closing_evidence` and
`command_skill_done`, beside the fail path that writes question.md. `code_step_start.py`
imports the evidence lines from it.

This is the second part of its queue item; the first moved the review-loop transcript reader to lib.

## Evidence

A move by concern. A new test fails while `code_step_boundary.py` is 1000 lines or more.

## Result

The new test fails before the move (1021 lines) and passes after it. The code-step suites pass with no change in
what any verb prints.

## Watch

None; no behavior change.

## Back-out

Revert `code_step_verification.py`, the moved functions and imports in `code_step_boundary.py` and
`code_step_closing.py`, the import edits in `code_step_hooks.py`, `code_step_gates.py`, `code_step_start.py`,
`code_step.py` and `tools/criteria_dry_run.py`, the `tests/run.sh` (both new modules) and `toolkit_paths.py` list entries, the
`test_code_step.py` module references and the new test.
