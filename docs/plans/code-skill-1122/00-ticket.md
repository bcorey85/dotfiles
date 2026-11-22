# Code skill fixes, November 2026

## Item: stopped-code-fork-s-coder-still-lands-work-after

Source: ~/agent-evals/queue/stopped-code-fork-s-coder-still-lands-work-after.md

---
type: "QueueItem"
title: "Stopped /code fork's coder still lands work after the d1de3385 fix"
description: "Stopping a /code fork stops its coder, or reports the live child, as the done item promised."
generated: {"by": "claude-code/opus-5-5", "at": "2026-11-22T11:46:26-06:00"}
kind: "chore"
status: "queued"
rank: 990
blocked_by: []
source: "skills/code/SKILL.md"
components: ["skill/code", "agent/code-fork", "agent/coder"]
not_dup: "regression: the done item (d1de3385) is closed, yet the same orphaned coder recurred on 2026-11-22 and the stop reported no live children"
---

## Context

Regression of queue/stopping-a-code-fork-leaves-its-coder-subagent.md (done, d1de3385). On 2026-11-22 TaskStop on a /code fork returned success and named no live children. Its coder kept running, rewrote a file the session had deleted after the cancel, and handed back a report. The session found the child only from that hand-back and stopped it by its id.

## Done when

- TaskStop on a /code fork stops the dispatched coder, or its result names the live child id.
- A replay of a cancel during the coder step writes nothing after the stop.

## Item: code-run-hold-drops-when-another-session-edits-its

Source: ~/agent-evals/queue/code-run-hold-drops-when-another-session-edits-its.md

---
type: "QueueItem"
title: "Code-run hold drops when another session edits its file mid-run"
description: "A /code phase review keeps holding a file another session owned at the phase start even after that session edits it again mid-run."
generated: {"by": "process:claude-code-session", "at": "2026-11-22T14:00:21-06:00"}
kind: "method"
status: "queued"
rank: 1007
blocked_by: []
source: "claude/.claude/skills/code/SKILL.md"
components: ["skill/code", "script/code-review-start"]
not_dup: "code-runs-hold-the-files-another-session-left (done 2026-11-09) holds a file only while its bytes match the phase-start hash; this item covers a file the other session keeps editing during the run, which loses the hold and reaches the fix coder"
---

## Context

A /code run in a checkout where another session was building a new lane for a different skill (one modified skill file, one untracked file). The run's coder brief named those files off-limits. After the run's two review loops, both files held edits that could not be attributed: the other session's work and the run's fix coder may both have written them. The 2026-11-09 fix holds a file only when it is still dirty with the same bytes as at the phase start, so a file the other session edited after the phase started is no longer held and the fix coder may edit it.

## Done when

- A file dirty at the phase start stays held for the whole phase even if its bytes change during the phase, and any change made to it during a coder call is named as a tool fault.
- An untracked file created by someone else during the phase (not by the run's coder) is not taken into the review scope.
- A test pins each case and fails without the change.

## Item: trim-the-code-skill-s-duplicated-prose-behind-rule

Source: ~/agent-evals/queue/trim-the-code-skill-s-duplicated-prose-behind-rule.md

---
type: "QueueItem"
title: "Trim the /code skill's duplicated prose behind rule-meter runs"
description: "Cutting the /code skill's duplicated prose saves about 300-450 of its 3028 words on every /code run (249 runs in November at work)."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T12:19:48-06:00"}
kind: "live-edit"
status: "queued"
rank: 1004
blocked_by: []
source: "QUEUE.md"
components: ["skill/code"]
---

## Context

A read of skills/code/SKILL.md found no dead references and about 82% of the text drives a model decision. Duplicates: the plan-impact owner rule (line 34, ~100 words cuttable, restates global CLAUDE.md), the dispatch-reviewer and waiting text (lines 28, 87, ~100 words, restate _shared/review-fork-run.md), the no-AskUserQuestion and stop text (lines 20, 26, ~50 words), release and stop wording also in agents/code-fork.md (~70 words). Exact-duplicate sentences (~150-250 words) are safe; every other cut is a rule change and needs rule-meter on/off runs.

## Done when

The exact duplicates are cut, each reworded or removed rule has meter counts in its change file, and the skill is 10-15% shorter.

## Comments

none
