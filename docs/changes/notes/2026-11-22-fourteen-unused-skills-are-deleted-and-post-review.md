---
type: "Change"
change_type: "removed"
title: "Fourteen unused skills are deleted and post-review folds into peer-review"
description: "vault-ask, vault-progress, vault-review, save-note, daily-recap, weekly-recap, msg, calibrate, falsify, eng-arch, pull-design, go and stop are deleted, and posting approved review comments moves into /peer-review as its step 8, so the skill list every session loads is 14 entries shorter."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T12:06:58-06:00"}
seq: 16
kind: "user-rule"
components: ["skill/peer-review", "skill/post-review", "skill/calibrate", "skill/eng-arch", "agent/code-reviewer", "agent/mutation-tester"]
evidence: ["user rule"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: ""
---

## Change

Deleted skills: vault-ask, vault-progress, vault-review, save-note, daily-recap, weekly-recap, msg (personal), calibrate,
falsify, eng-arch, pull-design, go, stop, post-review. Glossary stays.

`/peer-review` gains `### 8. Post the approved comments (+comment only)`: write the payload, run `check-anchors`
(moved from post-review into `skills/peer-review/`), hand the user one `gh api` POST line, then confirm with a GET.
The agent still never posts.

Dangling references fixed: `orient` (the `/daily-recap` capture line), `_shared/skimmable-writing.md` (`/eng-arch`),
`agents/mutation-tester.md` and `agents/code-reviewer.md` (`/calibrate`), and the deleted skills' entries in
`settings.json` `skillOverrides`. The ADR skill and template still say "eng-arch" for an architecture doc as a kind
of document, not the skill; left as is.

Not deleted, though asked: `brainstorm`, which holds the user's staged edits, and `escape`, which `/stage`,
`/peer-review` and `/branch-recap` invoke to log a defect caught by hand. Both went back to the user.

## Evidence

The user named each skill as unused.

## Result

`rg` finds no remaining call to a deleted skill under `claude/.claude/`.

## Watch

None. Skill calls are counted in `skill-usage.jsonl`, but a deleted skill has no reading to watch.

## Back-out

Revert the commit; the skill folders come back.
