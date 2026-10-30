---
type: "Change"
change_type: "fixed"
title: "a failed /code restart keeps the old run and its coder gate"
description: "A /code start --restart that fails while it builds the new run leaves the old run's state and its coder gate as they were, so the old run can still resume with its gate."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T06:21:19-05:00"}
seq: 332
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_restart_whose_new_run_fails_to_build_keeps_the_old_run_and_its_gate"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `start` clears the coder gate and then builds the new run. When the verb then fails (a crash or a nonzero exit,
  such as a failed coder packet), it now puts the gate file back to what it held before the clear. If there was no
  gate, it deletes the one the failed build set. The state file already stayed as it was, because a failed verb
  writes nothing, so the old run and its gate now stay together.
- That one restore replaces the packet-only clear in the dispatch build, which removed a half-set gate but never
  brought back the old one.

## Evidence

judgment: a restart whose new run failed to build kept the old state file but had already deleted its coder gate.
The old run looked alive, but its coder ran with no gate.

## Result

The named test fails before (the gate file is gone after the failed restart) and passes after. The test for a
failed packet on a first start still passes: no gate is left behind.

## Watch

None.

## Back-out

In `code_step_start.py`, delete `coder_gate_restored_on_failure` and `restore_coder_gate`, take the clear and the
start calls out of the `with` block, and put back the `try`/`except SystemExit` clear around `packet_text`. Remove
the test.
