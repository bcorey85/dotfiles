---
type: "Change"
title: "Cull the flow, plan, logging and ledger tests, and delete two dead telemetry scripts"
description: "Removed the skill-use and test-edit telemetry scripts, which no hook runs (the ledger hook writes those rows), and cut the tests that pinned them or that repeated a case another test already pins: 3693 tests become 3584, wall-clock 285s to 220s."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-29T09:04:21-05:00"}
seq: 245
kind: "fix"
components: ["script/log-skill-use", "script/test-edit-telemetry", "script/log-agent-usage", "script/calibration-guard", "script/emit-orchestration", "script/warn-skip-hooks", "script/telemetry-enabled", "script/agent-cost", "script/log-review-metrics", "script/refactor-flow", "script/adr-flow", "script/plan-format", "script/log-escape", "script/log-scan", "script/parallel-tests", "script/verify-prep", "script/verify-log", "skill/audit"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_ledger_hook.py::LedgerHookTest::test_the_ledger_on_path_gets_the_event_and_its_stdin"
asked: ""
proof: []
unmeasured: "Removes dead code and redundant tests; no intake number reads it."
---

## Change

- Deleted `telemetry/log_skill_use.py` and `telemetry/test_edit_telemetry.py` with their two test files, their `ruff.toml` entries and the `ALLOWED_HITS` entry in `test_toolkit_self_location.py`. `toolkit_paths.py` held no entry. The ledger hook now writes the skill-use and test-edit rows.
- Removed the cases of other tests that ran the two scripts (`test_telemetry_switch.py`, `test_review_fixes.py`).
- Dropped the parity tables and the jq-quirk tests from the shell-port tests (`test_log_agent_usage`, `test_calibration_guard`, `test_emit_orchestration`, `test_warn_skip_hooks`). Kept the pins on code-point counting, JSON types and the skip-hooks switch.
- Merged repeated cases into subTest tables: `test_telemetry_enabled`, `test_agent_cost`, `test_log_review_metrics`, `test_refactor_flow` (prune, verdict, rerun and bad-input tests), `test_verify_branch_script` (moved-line failures, untracked-file staleness, whitespace sign-off, late untracked file), `test_adr_flow` (keep-task-dir, refusal paths, hidden-from-status files, staged entries, relative and empty task dir), `test_plan_format` (gate clauses, deviation entries).
- Deleted tests whose pin lives in another test: the retired-variable tests in `test_log_escape` and `test_log_scan`, the within-limit test in `test_parallel_tests`, and in `test_verify_branch_script` the absent-id, NA ticket and manual-verification variant tests.
- Skipped: merging the full-run escape-already-logged test in `test_verify_branch_script` (a full run sent twice is refused with exit 2, so it cannot share state with the gap test); merging the repeated escapes-only test (kept as its own test); `test_non_object_usage_without_earlier_tokens_writes_no_row` (outside the listed ranges); the real pins `test_report_chars_counts_code_points`, `test_agent_and_model_keep_their_json_types` and `test_skip_hooks_is_not_honored`.

## Evidence

- Nothing runs the two scripts: `rg 'log_skill_use|test_edit_telemetry' claude/.claude tests/` found no call in `settings.json`, hooks, skills or other scripts. The remaining hits were their own tests, the cases above, the `ruff.toml` entries, a historic change file, their own docstrings, and prose in `claude/.claude/skills/audit/skills.md` (lines 7 and 14) that named `log_skill_use.py`; this change fixes that prose so the audit lane now reads the ledger's `skill_use` table.
- The `kind` is `fix` because it is the only kind that fits a no-behavior cleanup. The named test pins the replacement path: the ledger hook takes the event and its stdin, which is how the skill-use rows are written now.
- Before: 3693 tests in 99 files, wall-clock 284.8s. After: 3584 tests in 97 files, wall-clock 220.3s. 0 failed in both.

## Result

- Every edited test file passes. `ruff check` is clean on the changed test files. The suite's lint step failed before and after on complexity warnings (C901) in gate and lib scripts that this change does not touch.

## Watch

—

## Back-out

Revert the commit. The two scripts and their tests return.
