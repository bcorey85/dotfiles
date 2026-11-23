---
type: "Change"
change_type: "changed"
title: "The retro lane queues its own picks and reports a log of what it queued and skipped"
description: "The retro lane of the audit skill decides which of its candidates to queue, queues them, and ends with a log of the queued and the skipped ones, so the user no longer picks numbers."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-22T22:26:02-06:00"}
seq: 38
kind: "user-rule"
components: ["skill/audit"]
evidence: ["user request"]
watches: []
test: ""
asked: "2026-11-22: the user asked that the retro lane queue the items it judges worth a fix on its own, skip the rest, and report a log of both"
proof: []
unmeasured: "No rule-meter fixture shows this behavior: the lane reads a whole past session through the session search tool, and the meter's fixtures hold one task in one repo. No intake number reads it either: the lane runs by hand a few times a week."
---

## Change

`skills/audit/retro.md`:

- The report no longer ends by asking the user for the numbers to queue.
- A new `Queue` section tells the lane to decide each candidate itself. It queues a candidate when the moment lost
  work, wrote a wrong record, let a defect through unseen, or happened more than once, and when its matching queue
  item is closed and the moment came after that fix. It skips a candidate whose matching item is still open, and
  one that happened once and recovered with no help.
- The report is now a log in two lists, `Queued` and `Skipped`, each line with the queue file written or the reason
  for the skip.

`skills/audit/SKILL.md`: the boundary line that said the lane queues only the user's picks now says the lane queues
its own picks and logs both lists.

## Evidence

- user request: the user asked for the lane to queue on its own and report a log.

## Result

Applied by hand once, on the session that asked for it: five candidates, two queued, three skipped, each with its
reason. No meter run: see `unmeasured`.

## Watch

None: see `unmeasured`.

## Back-out

Revert the two files. The lane goes back to a numbered list and waits for the user's pick.
