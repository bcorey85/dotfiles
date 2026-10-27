---
type: "Change"
title: "code_step verification refusal names the phase and offers only a repo script"
description: "The refusal for a compound Automated Verification line names the phase each bad line belongs to, says every open phase is checked at each start, and offers only an executable repo script whose comments name no ticket or plan path."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:50:59-05:00"}
seq: 80
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_start_input.py::StartInputTest::test_a_compound_verification_line_names_its_phase_and_offers_only_an_executable_script"
asked: ""
proof: []
unmeasured: "Verification-shape refusals are not logged by reason; no intake number reads them."
---

## Change

Each problem line reads `plan:line: Phase N: <text> - <problem>`. The lead says every open phase is checked at each start.
The shape text says a check needing `&&`, a pipe, a subshell or an assignment goes in an executable repo script run as
`path/to/script args`, with comments that name no ticket or plan path. The old text led a session to try a shell wrapper
that a hook denies.

## Evidence

A Phase 3 line blocked a Phase 1 start; the session tried a shell wrapper (hook denied), then a script whose header
hit the comment gate: four extra round trips and one extra fork.

## Result

The refusal points at one form every hook allows and says which phase to fix.

## Watch

None.

## Back-out

Revert the commit.
