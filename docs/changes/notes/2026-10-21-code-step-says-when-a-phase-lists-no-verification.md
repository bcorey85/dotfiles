---
type: "Change"
change_type: "fixed"
title: "code-step says when a phase lists no verification commands and drops (last phase) when gated phases remain"
description: "When a phase lists no verification commands, the phase-done text says that none were run, not \"0 command(s) green\". The Phase N complete line leaves out \"(last phase)\" when only gated phases remain. after-review and the handback hook share one helper that puts a resumed review loop back."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T14:55:07-05:00"}
seq: 19
kind: "fix"
components: ["script/code-step"]
evidence: ["work incident", "tests"]
watches: []
---

## Change

- `scripts/code-step.py`:
  - `finish_phase` prints "The phase lists no verification commands, so none were run." when nothing ran, nothing was skipped, and the phase lists no commands after N/A items are removed. Other cases keep the old count line.
  - `block_b_or_c` prints "Phase N complete." without "(last phase)" when gated phases remain open. The next-step text still names `start --phase <id>`.
  - New `put_resumed_review_back` replaces the two copies of the review-loop flip in after-review and the handback hook. The state that each path writes does not change.
- `tests/scripts/test_code_step.py`: four new tests. Two check the new text. Two check that the old text stays where it is still true.

## Evidence

Work incidents: in one work slice, `skill-done` on a phase with no commands printed "0 command(s) green". In the same slice, the done text said "(last phase)" and then said that the plan was not complete, because only gated phases remained.

A code review found the change clean. One false line remains: `skill-done` on a closing phase that lists commands still prints the count line. The closing-phase template gives those phases no command list, so only a hand-edited plan reaches it.

## Result

Staged 2026-10-21 in the fourth script fix batch. 335 code-step and plan-format tests pass. The state-machine walk found 0 failing paths. Two of the four new tests fail against the installed script. Installed 2026-10-21. The full suite ran 1,481 tests in 39 files. One file failed, on a real plan that the criteria parser refuses, which this batch did not touch.

## Watch

None. No intake metric counts phase-done text.

## Back-out

Restore the previous `code-step.py` and `test_code_step.py` from the dotfiles history.
