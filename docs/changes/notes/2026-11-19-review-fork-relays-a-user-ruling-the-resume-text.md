---
type: "Change"
change_type: "fixed"
title: "Review fork relays a user ruling the resume text quotes"
description: "The review fork's stop footer asks a session that passes on the user's ruling to add a `user said: \"<words>\"` line, and the Resume step maps that line to `asks-done --by user --relayed-by <session> --quote \"<words>\"`, so a user-only ask closes through the fork."
generated: {"by": "process:lane-review-asks-rulings-2", "at": "2026-11-19T02:41:51-06:00"}
seq: 5
kind: "structured"
components: ["shared/review-fork-run"]
evidence: ["rule meter", "judgment"]
watches: []
test: ""
asked: ""
proof: ["2026-11-19-review-resume-relay-the-user-said-line-maps-to-the"]
unmeasured: "No intake number counts relayed user rulings refused by a user-only ask."
---

## Change

`skills/_shared/review-fork-run.md`: the STOP footer's next-to-last line also tells a session that passes on the
user's ruling to add `user said: "<the user's exact words>"`. The Resume paragraph passes
`--by user --relayed-by <session name> --quote "<words>"` in place of `--by session` when the resume text carries that
line and the stop lists an ask marked `[user only]`. `decide` takes `--by session` there, with the user's words in
`--ruling`. `docs/rule-anchors.md` names the new mapping. opencode loads the shared skill file from `~/.claude/skills`,
so no port exists to patch.

## Evidence

judgment: the resume rule mapped every `ruled by:` reply to `--by session`, which a user-only ask refuses, and the
resume text carried no quote to relay.

## Result

Rule meter RF05 (agent-evals bin/rule_meter_scenarios.json), sonnet, 3 runs per cell, review-stop.md on two user-only
asks planted in the fixture:

| Level | Rule on | Rule off |
|---|---|---|
| supportive | 3 of 3 | 0 of 3 |
| neutral | 3 of 3 | 0 of 3 |
| competing | 3 of 3 | 0 of 3 |
| all | 9 of 9 | 0 of 9 |

## Watch

—

## Back-out

Revert the footer clause and the `user said:` sentence in the Resume paragraph of `review-fork-run.md`.
