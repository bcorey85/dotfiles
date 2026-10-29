---
type: "Change"
change_type: "changed"
title: "Global CLAUDE.md: messages to another session stay under 150 words, with long content sent as a file path"
description: "Global CLAUDE.md: a message to another session stays under 150 words, and tables, logs, diffs and reports go to a file whose path the message carries."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-29T00:00:00-05:00"}
seq: 11
kind: "behavior"
components: ["rule/global-claude-md"]
evidence: ["census"]
watches: []
---

## Change

Global CLAUDE.md: a message to another session stays under 150 words, and tables, logs, diffs and reports go to a file whose path the message carries

## Evidence

census

### Anchor reasons

Anchor `CLAUDE.md`, section `## Messages to Other Sessions` (evidence: census):

About 40 words. A message to a peer Claude session stays under 150 words. Messages to and from the session's own subagents are exempt. The message carries the verdict, the numbers the receiver acts on and its next step. If the detail already lives in a file, the message sends the path. No file is made only to hold a message. Received messages were the largest single source of main-session context growth at work. Effect unmeasured. No hook. Loads in every main session and subagent.

## Result

At work, messages received from other sessions made 7.6% of main-session context growth, median 2641 tokens each, the largest single source. Check after the edit: the median size of a received message and the Read growth, in the same live-log census

## Watch

—

## Back-out

—
