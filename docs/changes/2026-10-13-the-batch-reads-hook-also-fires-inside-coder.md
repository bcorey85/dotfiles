---
type: "Change"
change_type: "changed"
title: "The batch-reads hook also fires inside coder subagents, reading the coder's own transcript"
description: "The batch-reads hook also fires inside coder subagents, reading the coder's own transcript; other subagents stay skipped."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-13T00:00:00-05:00"}
seq: 1
kind: "behavior"
components: ["script/batch-reads-nudge"]
evidence: ["census"]
watches: []
---

## Change

The batch-reads hook also fires inside coder subagents, reading the coder's own transcript; other subagents stay skipped

## Evidence

census

## Result

Work logs: 16% of coder responses, and 17% of coder cache read (about 255M Sonnet tokens a week), come after the third single-read response in a row. The main session cut such runs by a fifth after the hook went live; the same in coders is about 50M Sonnet cache-read tokens a week. Replay of a subagent transcript: fires once, on the third single read, for a coder; never for another agent type.

## Watch

the coder read census on the next two intakes, against weeks 38 to 42.

## Back-out

restore the `agent_id` skip in `decide`
