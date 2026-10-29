---
type: "Change"
change_type: "changed"
title: "Global rule: tell the user about a toolkit bug or inefficiency, then queue it in agent-evals"
description: "The global CLAUDE.md gains a section: a session that notices a toolkit bug or inefficiency tells the user first, then adds an agent-evals queue item, with no work content on the work machine."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T22:18:10-05:00"}
seq: 22
kind: "user-rule"
components: ["rule/global-claude-md"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-25: can you add something to my global claude.md - if you notice a bug or inefficiency, first notify the user then add it to the queue in the agent-evals repo"
proof: []
unmeasured: ""
---

## Change

`claude/.claude/CLAUDE.md` gains `## Bugs and Inefficiencies You Notice` after Quality Checks. When a session notices
a bug or an inefficiency in the toolkit (an agent, skill, command, hook, script or rule) or in how a session runs it,
it tells the user in that reply, then adds an item with `~/agent-evals/bin/build_queue.py new` and rebuilds the queue.
On the work machine the item holds only the toolkit part and what goes wrong, never work code, paths, ticket text or
tool output. If `~/agent-evals` is missing, the session says the item was not queued.

The scope is the toolkit, the reading of "a bug or inefficiency" that fits a queue whose only product is toolkit
changes; a bug in the user's own product code goes to that repo's tickets, not here. The work-machine clause keeps
work content out of a repo that syncs to this machine.

## Evidence

The user's request, quoted in `asked`.

## Result

The section adds 4 lines to the global file.

## Watch

None. No intake number counts noticed defects; the queue's own item count shows whether sessions use it.

## Back-out

Delete the section.
