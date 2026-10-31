---
type: "Change"
change_type: "removed"
title: "The main-session orchestration file is shorter: each skill now holds its own routing rules"
description: "The workflow routing block is out of the main-session orchestration file, because every rule in it except three is stated in the skill or agent that it governs."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-27T00:00:00-05:00"}
seq: 1
kind: "behavior"
components: ["rule/orchestration"]
evidence: ["removal round", "census", "judgment"]
watches: []
---

## Change

The main-session orchestration file is shorter, because each skill now holds its own routing rules. The workflow routing block left that file. It mapped each kind of request to the skill that owns it and retired the built-in look-alikes. The user types the skill commands, and every rule in the block except three is stated in the skill or agent that it governs.

## Evidence

removal round, census, judgment

## Result

Without the block, the main session still picked the same lane for 10 of 12 kinds of request. It lost the lane only when a request did not name the skill: sizing a ticket and listing repo debt. For those two, it did the work itself in the main session. A request about another person's PR went to the built-in code review, which is read-only. At work, the user typed 64 of 65 peer reviews and 41 of 51 triages. The block cost 1,153 tokens on every main-session request, about 10M Opus cache-read tokens a week. The three rules found nowhere else were dropped too: planning has no router, the ADR ships in the same PR, and the optional pre-PR pass, which the user does not use. The session start hook's warning for a missing file now names the delegation rules, not routing.

## Watch

—

## Back-out

restore the block from git.
