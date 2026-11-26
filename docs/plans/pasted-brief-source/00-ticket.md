# A lane forked with a pasted brief writes no queue Source line, so its criteria read as the user's

Source: ~/agent-evals/queue/a-lane-forked-with-a-pasted-brief-writes-no-queue.md

## Context

2026-11-22: plan_check owner now reads both spellings of a queue Source line. eng-spec phase 1 writes Source only when
the ticket is a queue file, so a lane forked with a pasted brief that restates a queue item still reads owner user.

## Done when

- The fork brief names the queue item path so phase 1 takes the file branch, or phase 1 writes Source for a brief that
  names one; a skill edit runs rule-meter arms.
- A replay of a pasted-brief lane prints owner session.
