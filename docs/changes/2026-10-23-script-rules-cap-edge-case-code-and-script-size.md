---
type: "Change"
title: "Script rules: cap edge-case code and script size"
description: "The toolkit script rules no longer ask for a route and a test for every change that can happen during a run. Only reported changes get a route, and the rest go to one fallback stop. A new Size section asks for a sighting before new code, reuse of shared helpers, a split before features in a script over 1000 lines, and a stop when a diff is more than twice its design estimate."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-23T23:15:01-05:00"}
seq: 8
kind: "behavior"
components: ["rule/toolkit-script-rules"]
evidence: ["census", "judgment"]
watches: []
---

## Change

- **Changes during a run:** a route only for a change that a session reported. Every other change goes to one fallback stop that names the state and the recovery command. Before, the rule said to handle and test each one.
- **Size, new section:**
  - New code needs a sighting, or a defect that fires on every run.
  - Search the shared modules and the other scripts before you write a helper.
  - No new verb, route or state field in a script over 1000 lines. Split or cut it first.
  - Report the real diff size against a design estimate. Stop before review when it is more than twice the estimate.

## Evidence

Census of the code-step.py fixes since 2026-10-19: 8 normal-path fixes (about 1170 lines), 7 edge cases with one sighting (about 460) and 6 fixes with no sighting (about 230). The script grew from 1421 to 3196 lines in five days. The open resume change came in at +603/-140, four times its design estimate. Most of the excess was routes for stops that no session reported. The user flagged the growth. Judgment: the old "handle each one" rule asked for that growth.

## Result

Applied to the rules file. The resume change was cut to match on the same day.

## Watch

None. No intake metric counts script lines. Check the size of code-step.py at the simplify pass.

## Back-out

Restore the "Changes during a run" section and delete the "Size" section in `docs/toolkit-script-rules.md`.
