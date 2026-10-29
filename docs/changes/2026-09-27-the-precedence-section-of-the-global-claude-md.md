---
type: "Change"
change_type: "removed"
title: "The Precedence section of the global CLAUDE.md, which ranked the user's current instruction over project"
description: "The Precedence section of the global CLAUDE.md, which ranked the user's current instruction over project, global and agent rules, was deleted."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-27T00:00:00-05:00"}
seq: 14
kind: "behavior"
components: ["rule/global-claude-md"]
evidence: ["removal round", "judgment"]
watches: []
---

## Change

The Precedence section of the global CLAUDE.md, which ranked the user's current instruction over project, global and agent rules, was deleted.

## Evidence

removal round, judgment

## Result

Run as the coder with and without it: no task showed a difference, and the platform already places the user's live instruction above loaded files. One side effect was seen elsewhere: a coder asked for tests against its own no-tests rule cited this section to write them, and another run without that citation refused. The user dispatches coders through the build command, which does not ask them for tests, so the conflict does not arise there. About 36 words, about 55 tokens on every main-session and subagent request, about 1.2M a week.

## Watch

—

## Back-out

restore the section from git.
