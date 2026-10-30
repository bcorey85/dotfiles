---
type: "Change"
change_type: "fixed"
title: "Gated phase starts in one step with the gate evidence in the coder packet"
description: "A gated phase starts with one caller message once the gate is met: start --phase takes the gate evidence and the coder packet carries it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T08:31:55-05:00"}
seq: 395
kind: "fix"
components: ["skill/code", "script/code-step", "agent/code-fork"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_start_input.py::GateEvidenceTest::test_a_gated_phase_started_with_gate_evidence_puts_the_evidence_in_the_coder_packet"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code_step.py start --phase <id> --gate-evidence "<who>, <when>: <quoted text>"` writes the gate condition and the evidence into the coder packet and tells the coder the caller released the gate with that evidence. The option is refused without `--phase` (task text included), on a phase with no gate clause and on a closing phase. The stop on the next gated phase, the code skill and the code-fork agent tell the caller to run that command in one step only after the user or the outside session has released the gate in their own words, quoted verbatim with the sender named in the evidence. The placeholder text is refused as evidence. The script still never judges a gate.

## Evidence

judgment

## Result

A gated phase could take several caller round trips to start: the stop on the gate, a coder dispatched with a packet that lacked the release so it stopped with no change, and a fork that would not forward the release without a second confirmation. The release now reaches the coder in the first start call.

## Watch

—

## Back-out

Revert the option, the packet section and the prose lines.
