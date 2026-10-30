---
type: "Change"
change_type: "changed"
title: "Code and review scripts reuse the lib helpers they copied"
description: "Nine copies of what scripts/lib owns now call the lib helper or are deleted; a hand-back reads the loop transcript once, and a crash packet is built from one shared empty outcome, and a test checks it carries every key a finished outcome has."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T18:04:24-05:00"}
seq: 285
kind: "fix"
components: ["script/handback", "script/review-loop-gate", "script/review-loop-script", "script/review-fix", "script/code-step", "script/coder-gate", "script/verify-common"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_script_utils.py::StateFilePathTest::test_every_character_outside_the_safe_set_becomes_an_underscore_and_the_suffix_is_added"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_loop_gate.write_run_row` calls `script_utils.telemetry_switch_on` instead of running `telemetry_enabled.sh`
  itself.
- `handback.py` loads the loop transcript once and scans it once for the open-work, unchecked-code and plan-edit gates,
  in the same order. A failed scan skips only the full-check gate, on one stderr line; the open-work and plan-edit
  checks still run.
- `script_utils.state_file_path` builds the state-file path for `handback_store`, `review_loop_gate` and
  `verify_common`, with one filename rule.
- `code_step_asks.split_asks_done_args` uses `script_utils.pop_repeated_option`.
- `coder_gate.append_gate_log` and the `calls.jsonl` write use `script_utils.append_jsonl`; the calls lock stays.
- `review_loop_packet.crash_outcome` fills a copy of one `EMPTY_OUTCOME`; a test checks the crash packet carries every
  key a finished outcome has.
- Deleted: `hook_input.jq_output` and `code_step_core.say_file` (no callers), and the `asksAlso` and review_fix
  `"repo"` state keys (no readers).

## Evidence

- A read-only simplify review listed each copy beside the lib helper it repeats. `crash_outcome` listed all outcome
  keys a second time, so a missed key crashed the crash path.

## Result

- The named test fails if the finished-loop outcome gains a key the crash outcome lacks.

## Watch

None: no behavior a work log reads changes.

## Back-out

Revert the commit.
