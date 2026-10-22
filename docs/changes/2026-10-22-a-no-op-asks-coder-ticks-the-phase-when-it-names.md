---
type: "Change"
title: "A no-op asks coder ticks the phase when it names where each ask is done"
description: "When the asks coder changes nothing, code-step now runs the phase's verification commands and ticks, if the report has one `ALREADY-DONE: <n> — <file:line>` line for every accepted ask and raises no blocker. Every other no-change report still stops."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-22T09:51:55-05:00"}
seq: 8
components: ["script/code-step"]
evidence: ["work incident"]
watches: []
---

## Change

- `scripts/code-step.py`:
  - The asks coder prompt tells the coder to add `ALREADY-DONE: <ask number> — <file:line>` for each ask that the code already does, and for no other ask.
  - New `already_done_ask_numbers`. A line counts only when its value, after a closing period, comma or semicolon, is a whole `file:line` and the file exists in the repo.
  - `after-coder`: when the asks coder changed nothing, every accepted ask has a valid line, and the report has no `/eng-spec`, plan-impact or coder flag, the phase goes to `finish_phase`. That runs the verification commands and ticks, as after a clean review.
  - Any other report from an unchanged tree goes to the old "no reviewable change" stop. This includes a failed edit, a blocked hook and a question.
  - New `finish_without_review`, shared with the docs-only path.
- Tests: `tests/scripts/test_code_step.py`.

## Evidence

- Work incident: the review raised one ask, the user confirmed it, and the code already did it. The asks coder changed nothing, so `after-coder` stopped with "no reviewable change". The phase's verification commands never ran, and the tick needed the user's word.

## Result

A confirmed ask that the code already meets no longer stops the run. A no-op report still stops when the coder could not apply an ask. Known gap: a real file outside the repo, such as `../x.ts:1`, counts as a location.

## Watch

None. The intake does not count `after-coder` stops by reason.

## Back-out

Remove the `everyAskAlreadyDone` branch from `after-coder` and the ALREADY-DONE prompt line in `code-step.py`.
