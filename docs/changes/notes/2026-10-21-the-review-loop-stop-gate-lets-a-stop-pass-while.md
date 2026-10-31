---
type: "Change"
change_type: "fixed"
title: "The review-loop stop gate lets a stop pass while the loop waits on its own agents"
description: "review-loop-gate.py no longer blocks a review loop's stop while one of the loop's background agents has not reported. The loop ends its turn to wait for each report, and the gate read every wait as an attempt to finish."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T07:29:17-05:00"}
seq: 3
kind: "fix"
components: ["script/review-loop-gate"]
evidence: ["transcript read", "census", "tests"]
watches: []
---

## Change

- `scripts/review-loop-gate.py`: on SubagentStop, the gate passes when the loop has a background dispatch that has not reported. A dispatch counts as reported when its task notification or its hand-back message reaches the loop. The final stop has no dispatch open, so the gate checks it as before: a full check after the last code change, and a review of every fix diff.
- `--check` names the open dispatches.
- New test file `tests/scripts/test_review_loop_gate.py`. The script had no tests.

## Evidence

Transcript read: in one loop read in full, the loop dispatched its reviewers and coders in the background and ended its turn after each dispatch to wait. The gate blocked 9 of those waits. One block made the loop run the full test suite while its reviewers were still out, and the code changed after that run.

Census: on this machine, 526 of 534 gate blocks fired while a dispatch was still out, across 214 loops. 195 of those loops dispatched in the background, although the foreground hook sets `run_in_background: false`. 157 of 204 loops ran the full check two or more times.

Work logs: the 9 long loops that the phase-time report details had 49 gate blocks in 302 loop responses. Each block forces one extra loop response, so about 16% of those responses came from false blocks.

## Result

Installed 2026-10-21. Before the install, a replay of the new check over 210 review-loop transcripts from this machine found no final stop that it lets through by mistake. The 6 new tests pass.

## Watch

None. The intake reports this gate's blocks only per run in `phase-time.txt`, and no watch metric reads that file. Read the `review-loop-gate.py` lines there after the ship: the blocks per long loop drop from about 5 to 1 or fewer.

## Back-out

Restore the previous `review-loop-gate.py` from the dotfiles history.
