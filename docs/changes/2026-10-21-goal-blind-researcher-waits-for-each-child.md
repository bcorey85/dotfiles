---
type: "Change"
title: "Goal-blind researcher waits for each child"
description: "The goal-blind researcher now waits for each child's completion notice and checks for the file it writes before the next step. It never ends its turn while a child runs."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T22:44:29-05:00"}
seq: 25
components: ["agent/goal-blind-researcher"]
evidence: ["work incident"]
watches: []
---

## Change

- `agents/goal-blind-researcher.md`, `## Steps`: a new opening paragraph. Run one child at a time, wait for its completion notice, then Glob for the file it writes. Never end the turn while a child runs. If the file is missing after the notice, name the step and stop.

## Evidence

- Work incident: on one eng-spec run, the researcher dispatched `spec-questions` and handed back before the child's completion notice arrived. No `01-questions.md` existed at hand-back. The session resumed the researcher with a message to wait for each child, and it then wrote the questions and research files. The second report did not reach the session, so nobody knows if the leak check ran.

## Result

The research phase returns only after all of its children finish, and a missing file stops the run with the step named. The session no longer resumes the researcher by hand.

## Watch

None. The intake has no metric for early hand-backs from this agent.

## Back-out

Delete the opening paragraph of `## Steps`.
