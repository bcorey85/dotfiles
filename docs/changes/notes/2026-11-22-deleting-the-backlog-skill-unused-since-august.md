---
type: "Change"
change_type: "removed"
title: "Deleting the backlog skill, unused since August, drops 286 words"
description: "The backlog skill (save a conversation's idea to docs/backlog/ for a later /eng-spec) ran 9 times at work, the last on 2026-08-10; deleting it removes a 286-word skill and one always-loaded description."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T23:56:07-06:00"}
seq: 46
kind: "user-rule"
components: ["skill/backlog"]
evidence: ["census"]
watches: []
test: ""
asked: "2026-11-22: the user asked to cut the backlog skill"
proof: []
unmeasured: "A deleted skill nobody calls leaves no work-log number to watch."
---

## Change

Deleted `skills/backlog/SKILL.md`. No agent, skill, command, script, test or settings entry names it.

## Evidence

Census. Work `skill-usage.jsonl` through 2026-11-20: 9 calls, the last on 2026-08-10, none in the fourteen weeks
since.

## Result

The toolkit loses a 286-word skill and its description from every session's skill list.

## Watch

None: see `unmeasured`.

## Back-out

`git revert` the commit.
