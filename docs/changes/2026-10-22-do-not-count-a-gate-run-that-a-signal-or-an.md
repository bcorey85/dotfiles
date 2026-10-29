---
type: "Change"
change_type: "fixed"
title: "Do not count a gate run that a signal or an interrupt ended"
description: "quality-check-cap.py no longer records a failed Bash run that the user interrupted or that a signal ended (exit 129 to 192, timeout kills included), so the cap allows the rerun."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-22T07:36:55-05:00"}
seq: 2
kind: "fix"
components: ["script/quality-check-cap", "script/hook-input"]
evidence: ["work incident"]
watches: []
---

## Change

- `scripts/hook_input.py`: new `exit_code_in_error_text(text)`. It reads N from the leading "Exit code N" of a PostToolUseFailure `error`, or returns None.
- `scripts/quality-check-cap.py`, failure path: the run is not recorded when top-level `is_interrupt` is true, or when the exit code is 129 to 192. Exit 128, 255, any other nonzero exit, and a missing exit code stay recorded.
- The old interrupt check read `tool_error.error_type`, a field Claude Code does not send, so it never fired. The old timeout check searched the whole error text, stdout included. Both are gone. A timeout ends with exit 143, or 137 from the kill backstop, and the signal range covers both.
- Tests: `tests/scripts/test_quality_check_cap.py` sends the real payload shape for an interrupt, a timeout, a signal kill, and an exit 1 whose output quotes the timeout text.

## Evidence

- Work incident: the review loop's full gate run died with exit 144 after a `pkill` from the same loop. The cap recorded it as a finished run and denied the rerun. The gate never finished, and the phase's review step reported a critical blocker on a clean diff.

## Result

A gate run that did not finish no longer uses up the cap, so the loop can run it again. A real failure still counts, whatever its output says.

## Watch

None. The intake reports cap blocks only as a weekly count in `review-queue.txt`, which the edit watch does not read, and the count does not split blocks by the exit code of the recorded run.

## Back-out

Remove the `is_interrupt` and signal-range checks from the failure path, and drop `exit_code_in_error_text` from hook_input.py.
