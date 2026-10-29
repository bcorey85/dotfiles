---
type: "Change"
change_type: "changed"
title: "coder-core: every test, lint, typecheck or build command runs with its full output in a `/tmp/` log"
description: "coder-core: every test, lint, typecheck or build command runs with its full output in a `/tmp/` log, read with Read or `rg`, and is never piped into `head`, `tail` or `grep`."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-09T00:00:00-05:00"}
seq: 9
kind: "behavior"
components: ["skill/coder-core"]
evidence: ["judgment"]
watches: []
---

## Change

coder-core: every test, lint, typecheck or build command runs with its full output in a `/tmp/` log, read with Read or `rg`, and is never piped into `head`, `tail` or `grep`. The shell-write ban gets one exception for that log

## Evidence

judgment

### Anchor reasons

Anchor `skills/coder-core/SKILL.md`, section `## Shell commands the hooks block (HARD RULE)` (evidence: hook block log, judgment):

The shell forms the hooks deny, and that one banned fragment denies the whole compound command: file writes through the shell, `sh -c` and `bash -c`, inline interpreters, and the rest of the list. Added by the user by judgment, with no ledger row. It rests on the same hook block log as the global CLAUDE.md hook list. Unproven as coder text: no round compared coder block counts with and without it. The check-log exception under `/tmp/` matches the check-cap hook's own deny text, which tells the coder to redirect a failed run to a log.

## Result

The ban on every `>` redirect conflicted with the check-cap hook, whose deny text tells the coder to redirect the failed run to a log. A coder that cut its only check output was denied a re-run and its phase stalled. One bench phase was voided this way.

## Watch

`quality-check-cap` rows in the hook block log, and runs that end right after one.

## Back-out

revert the two coder-core lines
