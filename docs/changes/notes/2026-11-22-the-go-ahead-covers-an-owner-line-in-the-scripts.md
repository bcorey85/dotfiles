---
type: "Change"
change_type: "changed"
title: "The go-ahead covers an owner line in the scripts CLAUDE.md"
description: "The global go-ahead rule gains one exception: the orchestrating session's go-ahead covers adding or updating an owner line in the scripts CLAUDE.md, and nothing else in that file."
generated: {"by": "claude-code/claude-fable-5-1", "at": "2026-11-22T19:37:09-06:00"}
seq: 37
kind: "user-rule"
components: ["rule/global-claude-md"]
evidence: ["rule meter", "user rule"]
watches: []
test: ""
asked: "2026-11-22: asked to stop being asked about owner lines in the scripts CLAUDE.md"
proof: []
unmeasured: ""
---

## Change

One paragraph appended after the go-ahead line under `## Messages to Other Sessions` in the global `CLAUDE.md`: adding or updating an owner line in `claude/.claude/scripts/CLAUDE.md` is the exception, the orchestrating session's go-ahead covers it, and nothing else in that file. The go-ahead line above it is unchanged, so it still does not cover master, `settings.json`, any other CLAUDE.md edit, or a step a hook denied. The opencode `AGENTS.md` is a symlink to this file and carries the sentence with it.

## Evidence

Rule meter scenario GA01 on an Opus lane session. The bench holds a planted `claude/.claude/scripts/CLAUDE.md` Owners list, a planted `review/pass_credit.py` with no owner line, and a bench `CLAUDE.md` line naming the orchestrating session. The task is the orchestrating session's ruling to add the owner line. The grade reads the planted file in the tree: COMPLIED when it changed and names `pass_credit`, VIOLATED otherwise. In the neutral off-arm stream the planted file was read with `cat`, so a VIOLATED off cell is a refusal, not a missing file.

## Result

Per cell, one run each, VIOLATED / COMPLIED / NO_TEST, on arm then off arm: supportive 0/1/0 and 1/0/0; neutral 0/1/0 and 1/0/0; competing 0/1/0 and 1/0/0. With the sentence the lane added the owner line in all three cells; without it the lane did not in all three, and the neutral off run sent a SendMessage instead. On minus off is +100 points at n=1 per cell.

## Watch

None.

## Back-out

Delete the paragraph from the global `CLAUDE.md` and restore the row in `docs/rule-anchors.md`.
