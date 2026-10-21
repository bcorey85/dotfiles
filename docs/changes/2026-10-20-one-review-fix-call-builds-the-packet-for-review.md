---
type: "Change"
title: "One review-fix call builds the packet for review and fix"
description: "A hook saves the review loop's hand-back. One review-fix.py call parses it, routes on its status, renders the user text, opens the asks in the editor and logs the rows, so /review and /fix leave the model only the asks and the closing line."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-20T18:56:02-05:00"}
seq: 10
components: ["skill/review", "skill/fix", "script/review-fix"]
evidence: ["census", "judgment"]
watches: ["review-fix-one-call"]
---

## Change

- New script `scripts/review-fix.py` (draft, not yet installed). Verbs:
  - `packet --skill review|fix`: reads the saved hand-back, refuses one older than the last review-loop dispatch, parses it, and prints an `ACTION:` line (`render-and-finish`, `present-asks`, `ask-user-plan-impact`, `stop`, `stop-parse-failure`) with the user text and the rows it logged.
  - `asks-done`: logs the user's answer to each ask.
  - `decide adopt|keep`: records a plan-impact ruling and prints the redispatch lines.
  - `hook dispatch|handback`: marks a review-loop dispatch and saves its hand-back, so the model never pastes the packet.
- `skills/review/SKILL.md` and `skills/fix/SKILL.md` (drafts): dispatch the loop, run `packet`, do what the `ACTION:` line says.

Settings entries the user adds (PreToolUse): matcher `Agent` runs `python3 ~/.claude/scripts/review-fix.py hook dispatch`, and the `SubagentHandback` matcher adds `python3 ~/.claude/scripts/review-fix.py hook handback`.

## Evidence

Work main sessions on Opus: `/review` 374 turns and 2,480 responses, `/fix` 364 turns and 2,058 responses. An audit of the skill text counted about 560 and 640 responses of fixed steps over the window. The model also re-typed the hand-back into a command: the median hand-back is 3,943 characters, the largest 7,128.

The parser read 294 of 297 real review-loop hand-backs with a status line on this machine. It refuses the other 3 as malformed. Every shape that first failed is a test. 69 tests pass.

## Result

Not installed.

## Watch

`review-fix-one-call`: main-session responses per turn for `/review` and `/fix`, expected down.

## Back-out

Restore the previous review and fix `SKILL.md` files, remove the two settings entries and delete the script.
