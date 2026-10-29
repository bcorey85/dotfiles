---
type: "Change"
change_type: "added"
title: "A new PostToolUse hook on Bash, Read, Grep and Glob"
description: "A new PostToolUse hook on Bash, Read, Grep and Glob."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-23T00:00:00-05:00"}
seq: 5
kind: "behavior"
components: ["script/batch-reads-nudge"]
evidence: ["census", "judgment"]
watches: []
---

## Change

A new PostToolUse hook on Bash, Read, Grep and Glob. When three main-session responses in a row each make exactly one read, it injects one line telling the model to request its remaining known reads together. It fires once per run of single-read responses, stays silent in subagents, keeps no state and fails open.

## Evidence

census, judgment

## Result

Work census: main-session responses outside planning carry 1.06 tool calls each, 78% of their Bash calls sit in runs of 3 or more Bash-only responses, and the response after a Bash file read or search carries 28% of main-session cache read, 97% of it Opus. A prose rule to chain shell commands was already loaded. Installed before its instrument check passed. In the smoke runs, the baseline made 5 to 6 reads per task, below the 10 the check needed, so the hook had little to act on. On the fix task it fired once, in the right place, and main-session responses went from 6 to 7, not down. Effect unmeasured. Any later baseline run that uses the live settings now carries the hook, so a comparison needs it switched off in the baseline arm. Live check: main-session responses per read call in the census, before and after.

## Watch

—

## Back-out

delete the settings entry.
