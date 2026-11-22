---
type: "Change"
change_type: "changed"
title: "The general-purpose agent's description sends read-only searches to Explore"
description: "The general-purpose agent's description now covers edits, builds, tests and design calls and points read-only searches at Explore, matching the orchestration rule; its scope line goes."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T10:50:52-06:00"}
seq: 7
kind: "user-rule"
components: ["agent/general-purpose"]
evidence: ["user request", "prompt audit"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: "Rule-meter runs pending: until both arms run, this edit stays uncommitted. A routing change shows in agent-usage dispatch counts by agent, but no watch is set until the meter runs."
---

## Change

`agents/general-purpose.md`:

- description: "…searching for code… When you are searching for a keyword or file and are not confident… use this agent"
  becomes "General-purpose agent for multi-step tasks that edit files, run a build or test, or judge a design. For
  read-only searches and lookups, use Explore."
- body: "Do what has been asked; nothing more, nothing less." is removed.

## Evidence

prompt audit against Opus 5.5: the description contradicted `orchestration.md`, which sends read-only lookups to
Explore on Haiku. The description is what the router reads.

## Result

Pending rule-meter runs.

## Watch

None: see `unmeasured`.

## Back-out

Restore the old description and the scope line.
