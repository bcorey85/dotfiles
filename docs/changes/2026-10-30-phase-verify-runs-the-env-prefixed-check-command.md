---
type: "Change"
change_type: "fixed"
title: "Phase verify runs the env-prefixed check command, not a prose span"
description: "A verification item whose command starts with env and assignments now runs that command; when no span is a known command, the last program span after the item's em dash wins over prose spans before it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T09:20:35-05:00"}
seq: 358
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_an_env_prefixed_command_wins_over_a_prose_program_span_before_it"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The command start that verify matches now accepts a leading `env`, with or without NAME=value assignments
  (`env CARGO_BUILD_JOBS=4 cargo test`, `env cargo test`). Such a command matches in the first pass, so a prose span
  earlier on the line is never reached.
- When no span is a known command, the fallback now prefers the last program span after the item's " — " over spans
  in the prose before it. Without a dash it takes the first such span, as before.

## Evidence

judgment: on a work repo an item whose command was `env CARGO_BUILD_JOBS=4 cargo test ...` came after a CLI name with
an argument in the acceptance note. Verify ran that installed binary against live data, failed the phase, and never
ran the real test.

## Result

The named test fails before (verify picks the prose `ls -la` span) and passes after.
`test_the_last_program_span_after_the_em_dash_wins_over_prose_spans_before_it` covers the fallback order.

## Watch

None.

## Back-out

Revert the two edits in `first_command_span` and `COMMAND_START` in `code_step_verification.py`.
