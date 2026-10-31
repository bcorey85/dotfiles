---
type: "Change"
change_type: "changed"
title: "The code skill's phase sign-off stop now tells the user to run /clear and then /code to start the next phase"
description: "The code skill's phase sign-off stop now tells the user to run /clear and then /code to start the next phase in a fresh context, and to confirm in place only to keep the current context."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-25T00:00:00-05:00"}
seq: 1
kind: "behavior"
components: ["skill/code"]
evidence: ["census", "judgment"]
watches: ["signoff-stop-clear-context"]
---

## Change

The code skill's phase sign-off stop now tells the user to run /clear and then /code to start the next phase in a fresh context, and to confirm in place only to keep the current context. The skill already resumes from the first unchecked phase in the plan's phase list. The auto-advance path does not change.

## Evidence

census, judgment

## Result

Work census: main-session responses outside planning carry 37% of all cache read, median context 113k. Every one of 518 compactions was automatic, and the sessions with one carry 85% of main-session cache read. Context falls from 165k before a compaction to 86k after it, and the prelude is about half of main-session cache read, which no reset touches. Sized cut: 74M to 727M Opus cache-read tokens a month, 1.7% to 16.8% of main-session cache read, with the low end likelier, for 1.3M to 9.1M fresh tokens to rebuild context. The stop already waits for the user, so the step adds no stop. Quality risk: a decision the user made in the conversation and did not write into the plan does not reach the next phase. Effect unmeasured. Live check: census sessions that open with /clear, compactions, and review findings per phase, before and after.

## Watch

Read 2026-10-24 on work logs through 2026-10-21: findings per code-reviewer run 3.86 after, against a median of 2.63 (range 2.10 to 4.74) before. No change. Kept: the step adds no stop and lost no review findings. Watch closed.

## Back-out

restore the prior step 2.
