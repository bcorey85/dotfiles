---
type: "Change"
change_type: "changed"
title: "The /code skill passes a closing skill only with no open finding"
description: "The /code skill's invoke-skill step now says which verdict to send: `skill-done pass` only when the closing skill reports no open finding, else `skill-done fail`. Before, it named both and gave no rule."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T00:11:34-05:00"}
seq: 3
kind: "behavior"
components: ["skill/code"]
evidence: ["peer report"]
watches: []
test: ""
unmeasured: "No work-log field records a closing skill's open findings next to the skill-done verdict."
---

## Change

- **`skills/code/SKILL.md`, the `invoke-skill` step:** run `skill-done pass` only when the skill reports no open finding. Otherwise run `skill-done fail`.

## Evidence

Peer report: one closing test-audit phase ran `skill-done pass` with 8 findings not fixed. The findings were fixed later through /fix, so nothing shipped unfixed. One sighting, so the script guard that refuses `pass` with open findings was dropped. The one line rides in skill text that the resume verb change rewrites anyway.

## Result

Built in the resume lane bundle. The review approved it. Installs with the resume verb change.

## Watch

None. See `unmeasured`. Add the script guard if a closing skill passes with open findings again.

## Back-out

Restore the `invoke-skill` line in `skills/code/SKILL.md` from the dotfiles history.
