---
type: "Change"
change_type: "fixed"
title: "The code skill runs each code-step verb alone so the coder prompt is not cut"
description: "The /code skill tells the subagent to run each code-step.py verb as its own Bash call, with no pipe, head, sed or second command. A cut output loses the coder prompt."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T16:57:27-05:00"}
seq: 21
kind: "fix"
components: ["skill/code"]
evidence: ["transcript read"]
watches: []
---

## Change

- `skills/code/SKILL.md` step 1: one sentence. Run each `code-step.py` verb as its own Bash call, with no pipe, `head`, `sed` or second command.

## Evidence

Transcript read: a scan of this machine's /code sessions compared each dispatch output with the next Agent call. In three sessions on one day, the subagent piped `code-step.py start` through `head` or `sed`. The output ended before the end of the prompt, so the coder packet was never sent. In one session the subagent did not dispatch, and the next verb found no coder report and left the state stuck. In two sessions the subagent wrote its own prompt. A fourth session cut a plan-edit prompt the same way. The skill said to pass the prompt verbatim but did not say to run the verb unpiped. No hook checks that the coder prompt holds the packet.

This is a wording fix and the first step only. The structural fix, a hook that denies a coder dispatch without the packet, is in design with the event-log change.

## Result

Edited 2026-10-21. No test covers skill text.

## Watch

None. No intake metric counts coder dispatches without the packet.

## Back-out

Delete the sentence from step 1.
