---
type: "Change"
change_type: "changed"
title: "Peer-session messages lose their 150-word cap"
description: "A message to a peer session is kept short and carries the verdict, the numbers and the next step, in place of a fixed 150-word cap."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T10:08:23-06:00"}
seq: 3
kind: "user-rule"
components: ["rule/global-claude-md"]
evidence: ["user request", "prompt audit"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: "Rule-meter runs pending: until both arms run, this edit stays uncommitted. No intake number reads peer-message length."
---

## Change

`CLAUDE.md`, `## Messages to Other Sessions`: "under 150 words" becomes "short". The rest of the paragraph (verdict,
numbers, next step, path not content) is unchanged.

## Evidence

user request after a `/doctor prompt-audit` run against Opus 5.5: a numeric cap makes the sender cut needed numbers or
pad, where the paragraph already says what a message must carry.

## Result

Pending rule-meter runs.

## Watch

None: see `unmeasured`.

## Back-out

Restore "under 150 words" in `CLAUDE.md`.
