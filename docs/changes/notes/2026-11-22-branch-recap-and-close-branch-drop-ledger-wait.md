---
type: "Change"
change_type: "fixed"
title: "Branch-recap and close-branch drop ledger wait seconds copied from a script"
description: "Branch-recap and close-branch keep the 600000 ms Bash timeout and drop the 204 s and 90 s figures copied from ledger_deferred.py, which drift when the script changes."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T10:50:52-06:00"}
seq: 9
kind: "user-rule"
components: ["skill/branch-recap", "skill/close-branch"]
evidence: ["user request", "prompt audit"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: "A fact correction: the step the model takes (one Bash call, 600000 timeout, no retry) is unchanged. No intake number reads it."
---

## Change

- `skills/branch-recap/SKILL.md`: "about 204 s when the ledger answers busy at once, longer when a ledger call hangs"
  becomes "on a busy or hung ledger it can take minutes"; "waits up to about 90 s for it to catch up" becomes "waits
  for it to catch up".
- `skills/close-branch/SKILL.md`: the same parenthesis change.

## Evidence

prompt audit: the seconds are internals of `ledger_deferred.py`. The only number the model acts on is the timeout.

## Result

Applied. No run: fact correction.

## Watch

None: see `unmeasured`.

## Back-out

Restore the seconds.
