---
type: "Change"
change_type: "changed"
title: "Ten toolkit scripts meet the readability limits"
description: "The ten scripts with the most readability hits are split into named steps with named return types; hits fall from 178 to 5, behavior and hook speed stay the same."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T23:10:54-06:00"}
seq: 14
kind: "user-rule"
components: ["script/shell-write-gate", "script/script-utils", "script/check-scope", "script/refactor-flow", "skill/refactor", "script/shell-command", "script/source-text", "script/coder-gate", "script/stale-prose", "script/review-loop-script", "script/plan-format"]
evidence: ["user rule"]
watches: []
test: ""
asked: "2026-11-08: yes to both"
proof: []
unmeasured: "A behavior-preserving refactor; the existing tests are the spec, so no intake number moves."
---

## Change

- `gates/shell_write_gate.py`, `lib/script_utils.py`, `lib/check_scope.py`, `skills/refactor/scripts/refactor_flow.py`, `lib/shell_command.py`, `lib/source_text.py`, `code/coder_gate.py`, `code/stale_prose.py`, `review/review_loop_script.py`, `lib/plan_format.py`: long and deeply nested functions split into named private steps; calls and ternaries inside call arguments named first; two-loop comprehensions written as for statements; tuples of three or more values returned as namedtuples; internal functions with more than five parameters take one named object.
- Every signature another file or a test calls is unchanged (returned tuples became namedtuples, which still unpack), except `review_loop_script.telemetry`, which is removed; its one caller, test_fix_induced.py, now calls `write_telemetry(repo, TelemetryRun(...))`. Messages and JSON fields are unchanged. `run_loop` and `record_plan_impact` now take one named object; `command_outcomes`, `scoped_result`, `log_gate_run`, `scan_words`, `scan_make` and `scan_target` take fewer parameters, with related values grouped into a namedtuple. Nothing outside their own file calls any of them.
- The hooks load no new module: coder_gate, shell_write_gate, check_scope and script_utils use `collections.namedtuple`; source_text already imported `typing` and `dataclasses`.

## Evidence

Hits from `code/readability_check.py` with every line of each file counted as written, before → after: shell_write_gate 28 → 0, review_loop_script 24 → 1, shell_command 23 → 0, source_text 22 → 0, plan_format 18 → 1, stale_prose 16 → 0, refactor_flow 15 → 0, script_utils 14 → 3, coder_gate 14 → 0, check_scope 4 → 0. Total 178 → 5.

## Result

Five hits stay, each a parameter count on a function other files or tests call: `script_utils.run_process` (6), `run_or_raise` (8), `run_retrying` (7), `plan_format.ruling_deviation` (6), and in review_loop_script `LoopRun.__init__` (6).

Hook timing, median of 30 PreToolUse Bash calls, HEAD then branch, two rounds (`python3 -c pass` 8.2 ms): shell_write_gate 37.0 → 37.6 ms, coder_gate bash-hook 33.6 → 34.4 ms. A first draft that imported `dataclasses` and `typing` on the hook path measured 42 ms and 43 ms; those imports were replaced.

`bash tests/run.sh`: 3227 tests in 124 files, 0 failed. Lint passes on all ten files.

## Watch

None; see `unmeasured`.

## Back-out

Revert the branch commit; no state file changed.
