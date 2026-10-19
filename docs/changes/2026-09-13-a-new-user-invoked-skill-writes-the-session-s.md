---
type: "Change"
title: "A new user-invoked skill writes the session's state at a task boundary — what shipped, what was decided"
description: "A new user-invoked skill writes the session's state at a task boundary — what shipped, what was decided, the numbers to keep, what is open, the rules that bind the next step, and the files to reopen — to a handoff file outside the repo."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-13T00:00:00-05:00"}
seq: 3
components: ["skill/handoff"]
evidence: ["token census", "judgment"]
watches: []
---

## Change

A new user-invoked skill writes the session's state at a task boundary — what shipped, what was decided, the numbers to keep, what is open, the rules that bind the next step, and the files to reopen — to a handoff file outside the repo, keyed by the checkout and by the terminal so two sessions in one checkout do not collide, so the user can clear the conversation and start the next task from disk rather than from an automatic compaction summary.

## Evidence

token census, judgment

## Result

The main session, not any subagent, spends nearly all of the tokens, and almost all of that is the context re-read on every turn, so the lever is how long a conversation runs before it resets. Read from the transcripts, an automatic compaction fires at about a hundred and fifty thousand tokens of context, spends about four thousand output tokens on its summary, and leaves the next turn about sixty-four thousand tokens of context. A written handoff and a clear is estimated at about two thousand output tokens and leaves about forty thousand, so it costs less per reset and per turn than either the current window or a lowered one. The window stays where it is and the reset moves to the task boundary. Not yet measured under use.

## Watch

—

## Back-out

—
