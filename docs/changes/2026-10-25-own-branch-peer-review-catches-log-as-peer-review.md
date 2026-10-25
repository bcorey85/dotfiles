---
type: "Change"
title: "Own-branch /peer-review catches log as peer-review escapes; each run logs own-branch or teammate"
description: "/escape gains a peer-review stage; /peer-review logs one row per run saying whether the PR is the user's own, and on an own-branch run hands each kept defect to /escape."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T15:45:37-05:00"}
seq: 4
kind: "user-rule"
components: ["skill/escape", "skill/peer-review"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-25: a lot of time that pr review is ME using /peer-review on my own local branch; we need to separate peer-review that i self run from runs i do on other teammates branches"
proof: []
unmeasured: ""
---

## Change

- `/escape` step 1 lists `peer-review` as a `stage_found`: the user's own `/peer-review` run on their own branch, after the gates. A catch on a teammate's branch is no escape.
- `/peer-review` step 1 sets `caller` to `own-branch` when the PR author's login equals the `gh` user, else `teammate`, and writes one `review_scope` row `{skill: "peer-review", caller}` through `ledger-write` while telemetry is on. With no ledger it lands in `skill-usage.jsonl`, whose scrub already lets `caller` cross.
- `/peer-review` step 7, own-branch runs only: each kept `blocker`, `ask` or `fix` goes to `/escape` with `stage_found=peer-review`. Teammate runs log no escape.
- The skill description and opening line say the PR can be the user's own.

## Evidence

The user runs `/peer-review` on their own branch before others read it, and those catches had no stage of their own: they landed as `pr-human` or went unlogged. The 72 work `/peer-review` runs log only `skill`, `via` and `repo`, so own-branch and teammate runs could not be told apart.

## Result

Checked on the jsonl path (no ledger on PATH): the run row writes `{"skill":"peer-review","caller":"own-branch",...}` and `log-escape stage_found=peer-review ...` writes a row that keeps the value. With the ledger on PATH all three new values fold to `other` until the ledger registry adds them; that request went to the ledger repo. The `log-escape` header comment still lists the old stage values: the write-edit gate blocked the comment edit.

## Watch

None. There is no baseline: the first own-branch counts and peer-review escapes arrive with the next intake, read by hand per the intake checklist.

## Back-out

Revert the edits to `claude/.claude/skills/escape/SKILL.md` and `claude/.claude/skills/peer-review/SKILL.md`.
