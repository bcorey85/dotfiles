---
type: "Change"
title: "code-step start stops at an open gated phase"
description: "When an open phase with a gate clause comes before the next ungated phase, `start` now stops and starts nothing. Before, it skipped the gated phases and started a later one."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-22T09:51:54-05:00"}
seq: 5
components: ["script/code-step"]
evidence: ["work incident"]
watches: []
---

## Change

- `scripts/code-step.py`:
  - New `gate_blockers(pending)` returns the open gated phases ahead of the first open ungated phase, and that phase.
  - `start` stops when a gated phase comes first. The stop text names each gated phase and its gate, names the next ungated phase, and says that `start --phase <id>` runs one anyway.
  - At phase end, a gated phase ahead makes the current phase the last one of the run. The next-step text uses the same stop text.
  - The "Skipped the open phases with a gate clause" output is gone.
- `start --phase <id>` still runs any open phase.
- Tests: `tests/scripts/test_code_step.py`.

## Evidence

- Work incident: on a branch with no feature code, `start` skipped gated Phases 0 to 7 and started Phase 8, the closing refactor. The gate waited on another ticket's merge. code-step cannot tell whether a later phase depends on a gated one.

## Result

A run never starts a phase past an open gated phase. The user decides each gate.

## Watch

None. No intake metric counts gated-phase stops.

## Back-out

Restore the skip in `start` and the `skipped_gate_line` text in `code-step.py` from git.
