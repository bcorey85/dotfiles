---
type: "Change"
change_type: "changed"
title: "Sign-offs record who and when, not the user's words"
description: "A sign-off that overrides a ticket criterion or moves a phase now records who signed off and when. It no longer quotes the user."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-23T08:16:58-05:00"}
seq: 2
kind: "behavior"
components: ["rule/global-claude-md", "agent/plan-verifier", "skill/verify-branch", "skill/plan-format"]
evidence: ["judgment"]
watches: []
---

## Change

- Global `CLAUDE.md`, Ticket Acceptance Criteria: "Record each sign-off with who and when." Before, it said "who, when and their words".
- `agents/plan-verifier.md`: an `overridden` criterion passes when the plan records the sign-off (who and when). Before, the plan had to quote it. The output table says "sign-off recorded".
- `skills/verify-branch/SKILL.md`: the `signoff` field is "who and when". An `overridden` row without a sign-off is a gap. Before, the row needed a quoted sign-off.
- `skills/_shared/plan-format.md`: a moved phase names the user's sign-off as who and when.
- The two script messages that ask for the user's words (`plan_format.py`, `code-step.py --ruling`) change in the next code-step bundle. The `--ruling` text becomes the user's decision in one line.

## Evidence

- Judgment: the user does not want quotes of themself in records. They approved this change on 2026-10-23.

## Result

The rule text asks for who and when. `verify-log` already checks only that `signoff` is not empty, so no script check changes.

## Watch

None. No intake metric reads the sign-off text.

## Back-out

Restore the five files from git.
