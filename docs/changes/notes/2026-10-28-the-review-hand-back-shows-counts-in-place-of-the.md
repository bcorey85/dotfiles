---
type: "Change"
change_type: "changed"
title: "The review hand-back shows counts in place of the fixed nit and skipped lists"
description: "handback.render drops the Fixed, Nits and Skipped lists from the user text of /review, /fix and code_step and prints one count line, such as Fixed 4, nits 2, skipped 1. Open blockers (the stop statuses), remaining and deferred findings, blocked agents, asks, check lines and the class-closure line stay; a fixed blocker is counted under Fixed. The logged rows are unchanged."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T20:39:38-05:00"}
seq: 234
kind: "user-rule"
components: ["script/handback"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-28: i dont want to see review fix / nits / skipped in main session - i never read them"
proof: []
unmeasured: ""
---

## Change

- `handback.render`: the first line is `Fixed N, nits N, skipped N`. The Fixed, Nits and Skipped sections are gone, with their unused helpers.

## Evidence

- The user's words, quoted in `asked`.

## Result

- Tests that asserted on listed text now assert the count line. The packet parse checks moved to `test_handback.ParseTest`, against `handback.load`.
- `handback.is_blocker` stays: the one-ask-per-finding fold uses it to mark an ask a blocker.

## Watch

—

## Back-out

Revert the commit. The lists show again.
