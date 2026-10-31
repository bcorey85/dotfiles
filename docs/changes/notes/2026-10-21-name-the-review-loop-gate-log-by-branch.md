---
type: "Change"
change_type: "fixed"
title: "Name the review-loop gate log by branch"
description: "The review loop's full gate run now writes to /tmp/review-gate-<branch>.log, not one shared /tmp/review-gate.log that other sessions overwrite."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T22:53:46-05:00"}
seq: 26
kind: "fix"
components: ["agent/review-loop"]
evidence: ["work incident"]
watches: []
---

## Change

- `agents/review-loop.md`, Step 6: the execution gate redirects to `/tmp/review-gate-<branch>.log`. The branch name is written literally, with each `/` as `-`.
- The hook that checks for the gate run matches any `review-gate[\w.-]*.log` path, so it accepts the new name with no script change. A branch name is letters, digits, `-`, `.` and `_` after the `/` swap.

## Evidence

- Work incident: on one /code phase, the loop's gate log in `/tmp` was overwritten by a review loop in another session. The loop then read the other session's results.

## Result

Each branch has its own gate log, so parallel sessions on different branches no longer read each other's failures. Two sessions on one branch still share a log.

## Watch

None. The intake has no metric for a gate log read from another session.

## Back-out

Put back `/tmp/review-gate.log` in Step 6.
