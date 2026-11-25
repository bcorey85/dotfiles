---
type: "Change"
change_type: "fixed"
title: "Announced-step gate skips drafted text in fences and quotes"
description: "The announced-step check drops fenced blocks and blockquote lines first, so a reply drafted for the user to send no longer reads as the session's own promise."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T14:16:43-06:00"}
seq: 4
kind: "fix"
components: ["script/staged-claim-gate"]
evidence: ["queue: staged-claim-gate-flags-first-person-promises"]
watches: []
test: "tests/scripts/test_announced_step.py::AnnouncedStepTest::test_draft_blocks_with_first_person_promises_pass"
asked: ""
proof: []
unmeasured: "A Stop-hook false positive with no logged rate; the cost is one extra turn per hit."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- `lib/message_text.py`: new `without_draft_blocks(text)` removes fenced blocks (backticks or tildes) and `>` blockquote lines.
- `gates/announced_step.py` reads the message through it before the quoted-span pass.

## Evidence

A drafted reviewer reply in the user's voice ("I am fixing X") was read as the session promising work, and the turn was sent back.

## Result

The new tests fail before the change and pass after. A plain promise outside the draft still blocks.

## Watch

None.

## Back-out

Revert the commit.
