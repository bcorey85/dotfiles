---
type: "Change"
title: "One review-fix call builds the packet for review and fix"
description: "A hook saves the review loop's hand-back and the commit gate refuses a false clean mark. One review-fix.py call parses it, routes on its status, renders the user text, opens the asks in the editor and logs the rows, so /review and /fix leave the model only the asks and the closing line."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-20T18:56:02-05:00"}
seq: 10
components: ["skill/review", "skill/fix", "script/review-fix", "script/handback", "script/review-commit-gate"]
evidence: ["census", "judgment"]
watches: ["review-fix-one-call"]
---

## Change

- New script `scripts/handback.py`. It is the one reader of the review-loop hand-back packet and keeps a per-session store of hand-backs under `~/.claude/state/handback/`.
  - `hook dispatch|handback`: a PreToolUse hook. `dispatch` records each review-loop dispatch. `handback` checks and records each review-loop hand-back, and denies a bad packet once per agent so the loop repairs it.
  - `check`: reads a packet on stdin and exits non-zero with the reason when the packet would be rejected.
  - `latest <session id>`: prints the session's latest dispatch and hand-back.
  - `false_clean_reason(session)`: the one rule for whether a session may mark the review gate clean.
- New script `scripts/text_utils.py`: generic helpers that `handback.py` imports.
- New script `scripts/review-fix.py`. Verbs:
  - `packet --skill review|fix`: reads the stored hand-back, refuses one older than the last review-loop dispatch, parses it, and prints an `ACTION:` line (`render-and-finish`, `present-asks`, `ask-user-plan-impact`, `stop`, `stop-parse-failure`, `stop-no-handback`) with the user text and the rows it logged.
  - `escape`: logs escape rows from the saved packet state.
  - `asks-done`: logs the user's answer to each ask.
  - `decide adopt|keep|discuss`: records a plan-impact ruling and prints the redispatch lines.
- `scripts/review-commit-gate.py`: a clean mark on the review gate is denied unless this session's latest stored hand-back is converged or deferred. The gate imports `handback.py` only when it checks a clean mark. A missing module gives the gate's internal-error prompt for that mark and leaves the commit check and the dirty mark working.
- `skills/review/SKILL.md` and `skills/fix/SKILL.md`: dispatch the loop, run `packet`, do what the `ACTION:` line says.

Settings entries (PreToolUse): matcher `Agent` runs `python3 ~/.claude/scripts/handback.py hook dispatch`, and the `SubagentHandback` matcher runs `python3 ~/.claude/scripts/handback.py hook handback`. The model never pastes the packet.

## Evidence

Work main sessions on Opus: `/review` 374 turns and 2,480 responses, `/fix` 364 turns and 2,058 responses. An audit of the skill text counted about 560 and 640 responses of fixed steps over the window. The model also re-typed the hand-back into a command: the median hand-back is 3,943 characters, the largest 7,128.

The parser read 294 of 297 real review-loop hand-backs with a status line on this machine. It refuses the other 3 as malformed. Every shape that first failed is a test. 69 tests pass.

## Result

Installed 2026-10-20 with both settings entries. Known gap: no captured hook event exists, so the hook tests use events built from the documented shape. A resumed /code run in a new session must run a review again before it can mark clean. No work-log reading yet.

## Watch

`review-fix-one-call`: main-session responses per turn for `/review` and `/fix`, expected down.

## Back-out

Restore the previous review and fix `SKILL.md` files, remove the two settings entries, reinstall the previous `review-commit-gate.py`, and delete `review-fix.py`, `handback.py` and `text_utils.py`.
