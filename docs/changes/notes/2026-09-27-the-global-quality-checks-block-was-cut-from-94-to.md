---
type: "Change"
change_type: "changed"
title: "The global quality-checks block is now about 30 words, down from 94"
description: "The global quality-checks block is now about 30 words, down from 94: coders run only the tests for the files they changed, the full suite runs once at the end of review, and a failing approach gets three attempts before a stop."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-27T00:00:00-05:00"}
seq: 13
kind: "behavior"
components: ["agent/review-loop"]
evidence: ["removal round"]
watches: []
---

## Change

The global quality-checks block is now about 30 words, down from 94: coders run only the tests for the files they changed, the full suite runs once at the end of review, and a failing approach gets three attempts before a stop. The instruction to run the full suite once before declaring done outside a review loop was removed.

## Evidence

removal round

### Anchor reasons

Anchor `CLAUDE.md`, section `## Quality Checks` (evidence: removal round):

About 30 words. Coders run targeted tests only, the full suite runs once at the end of review, and three attempts before a stop. Without the old block the main session ran the full suite less and missed nothing in one test, and without any attempt limit the coder overran it. The quality-check cap hook and the loop stop hook enforce parts. Loads in every main session and subagent.

## Result

Run as a plain main session with no coder, on a one-module fix and a fix that breaks a test in another module, each with a 75-second full suite. With the old block the session ran the full suite on both tasks, 150 seconds of waiting. With no block it ran it once, and with the short block not at all, using only the targeted test file. Every version left the other module's test passing and reported the risk, but that break was visible by reading the code, so the missed-break risk of skipping the full suite outside a review loop is untested. On a task whose dependency could never install, run as the coder, no block led to 5 failed commands, 3 repeats of the failing build and 2 failed diagnostics, before a hook stopped it. The old block stopped after 1 and the short one after 3, so the attempt limit stays. The coder's own skill already carries the targeted-tests rule, so the coder side only repeats it. About 110 fewer tokens a request, about 2.4M a week. One run per task.

## Watch

—

## Back-out

restore the block from git.
