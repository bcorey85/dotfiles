---
type: "Change"
title: "The review loop's run-logging glossary stops claiming that its disposition counts sum"
description: "The review loop's run-logging glossary stops claiming that its disposition counts sum."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-20T00:00:00-05:00"}
seq: 14
components: ["agent/review-loop"]
evidence: ["census"]
watches: []
---

## Change

The review loop's run-logging glossary stops claiming that its disposition counts sum. One of the three terms in that claim is not a field of the row it governs. Routing sends some findings marked for fixing to other buckets by design, so the claim marked specified behavior as a logging fault.

## Evidence

census

### Anchor reasons

Anchor `agents/review-loop.md`, section `## Step 7: Log the run (every invocation — the loop's flywheel)` (evidence: removal round, census, judgment):

The metrics line by absolute path, and the field glossary. The trimmed arm dropped the reasons. Consistent rows were 9 against 8, with the misses in the plan-impact and deferred exits of both arms. The glossary now denies that the disposition counts sum. One of the three terms in the old claim is not a field of that row. The other two disagree in 4 of 25 saved rows. The metrics line no longer carries the specialist counter or the specialist list, because the loop has neither. By judgment, the smell count now counts the structure findings of the code reviewer's structure step and of the Opus structure reviewer.

## Result

Effect unmeasured. Live check at the next intake: the share of logged rows whose counts fail the old sum. That share is a property of the routing and stays where it is.

## Watch

—

## Back-out

—
