---
type: "Change"
change_type: "removed"
title: "Deleting the guide skill, unused since September, drops 1210 words"
description: "The guide skill (write a JSON batch of judgment calls for a separate guide program to put to the user) ran 4 times at work, all on 2026-09-01, and never since; its program is not installed here, so deleting it removes a 1210-word skill and one always-loaded description."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T23:43:42-06:00"}
seq: 45
kind: "user-rule"
components: ["skill/guide"]
evidence: ["census"]
watches: []
test: ""
asked: "2026-11-22: the user does not use the guide skill; deletion and simplification is a priority equal to additions"
proof: []
unmeasured: "A deleted skill nobody calls leaves no work-log number to watch."
---

## Change

Deleted `skills/guide/SKILL.md` and its `user-invocable-only` entry in `settings.json` `skillOverrides`. No agent,
skill, command or script names it.

## Evidence

Census. Work `skill-usage.jsonl` through 2026-11-20: 4 calls, all on 2026-09-01, none in the eleven weeks since. The
`guide` program the skill drives is not installed on this machine.

## Result

The toolkit loses a 1210-word skill and its description from every session's skill list.

## Watch

None: see `unmeasured`.

## Back-out

`git revert` the commit.
