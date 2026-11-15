---
type: "Change"
change_type: "changed"
title: "A session that forks a lane keeps the user in its own pane"
description: "The orchestration rules now tell a session that forks a lane to name the fork, say it reports here and pass its reports on, and never to send the user to another pane to switch or to answer a question."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-15T13:33:38-06:00"}
seq: 5
kind: "user-rule"
components: ["rule/orchestration"]
evidence: ["user rule", "rule meter"]
watches: []
test: "tests/scripts/test_guidance_rules.py"
asked: "2026-11-15: asked by the user"
proof: ["2026-11-15-two-reworded-lane-rules-keep-the-user-in-the"]
unmeasured: "Whether the starting session passes on what the lane sends; the meter grades only where the session sends the user."
---

## Change

- `claude/.claude/orchestration.md`, Git, worktree bullet: the brief now also names this session, read from
  ListAgents, as the session the fork reports to, and says the fork sends every question for the user and its result
  there with SendMessage and never asks in its own pane. "Then tell the user to switch there, and do no more work in this
  session" became "Then tell the user the fork's name and that it reports here; never tell the user to switch panes.
  Do no more work on that task in this session, and pass on to the user what the fork sends."
- Same file, input-box bullet: "tell the user to answer in that pane" became "and never tell the user to answer in
  another pane. Put the question to the user in this pane, then send that session the user's own words with
  SendMessage, quoted and dated; never a paraphrase, and never your own go-ahead worded as the user's."
- `tests/scripts/test_guidance_rules.py` pins both lines. `docs/rule-anchors.md`: the Git row carries its new hash and
  links this change.

## Evidence

The user asked for it on 2026-11-15, after a session forked a lane and told the user to switch to the lane's
workspace. The old rule text told it to. The 2026-10-27 rule already routes a lane's commands through the session
that started it; these two lines still sent the user to the lane for everything else.

## Result

Rule meter, Sonnet, competing level, 8 runs per arm, runs that kept the user in the pane: the hand-over sentence 8 of
8 with it and 0 of 8 without; the lane-question line 7 of 8 with it and 2 of 8 without. The old sentences held 0 of 8.
The brief clause, graded on the brief each run wrote: 8 of 8 briefs with it route the fork's questions to the starting
session, and 5 of 8 without it by the detector. Those 5 say to report "when you need a decision"; none names a question
for the user or bans asking in the fork's pane, so a hand read gives 0 of 8.
Finding: `2026-11-15-two-reworded-lane-rules-keep-the-user-in-the`.

Sweep: no other line or printed message under `claude/.claude` sends the user to a worker pane.

Cut from the queue item by `agent-evals-a9` (session, not the user), 2026-11-15: a report to the user "on a fixed
interval while it runs". The session reports when the lane sends something.

Cost: every question and report from a lane now starts a turn in the session that forked it, which re-reads that
session's context. Not measured.

## Watch

None. No intake number counts the times a session sends the user to another pane.

## Back-out

Restore the two old sentences in `orchestration.md`, the old assertions in `test_guidance_rules.py` and the Git row's
old hash in `docs/rule-anchors.md`.
