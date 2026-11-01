---
type: "Change"
change_type: "added"
title: "Warn when /code starts on a main context over 100k"
description: "A typed /code run start whose main session already holds more than 100k tokens of context gets a one-line warning to clear first. The check rides in the existing UserPromptSubmit hook, format_changed.py, so no new process starts."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T01:35:22-06:00"}
seq: 448
kind: "user-rule"
components: ["script/format-changed", "script/code-context"]
evidence: ["census", "judgment"]
watches: ["code-context-warn-main-cache-read"]
test: ""
asked: "2026-11-01: on a warning when /code starts on a large main context, \"7. k but i usually clear\""
proof: []
unmeasured: ""
overlap: "The watches code-no-asks-main-cache-read (expected down) and code-plain-steps-main-cache-read (expected flat) read the same metric for /code turns from the same week, so this watch cannot be told apart from them. The direct reading is the intake's code-turn-parts table of context at start: the share of /code runs in the 100k to 200k band falls when the warning works."
---

## Change

`scripts/lib/code_context.py` reads the newest main-session reply from the end of the session transcript and adds its fresh input, cache write and cache read. On a typed `/code` prompt (not `/code resume`, not another skill that starts with code) above 100k, it returns a `systemMessage` that names the size and says to run /clear and then /code again. `format_changed.py`, already registered on UserPromptSubmit, prints it before its own git work. Every other prompt prints nothing.

## Evidence

The work intake's code-turn-parts table for runs from 2026-10-19 on puts 55 of 132 /code runs at a start context of 100k to 200k. Those runs have a median main cache read of 1.31M, against 688k for the 67 runs that start at 50k to 100k.

Hook cost, median of 30 runs on a 138 MB transcript: bare `python3 -c pass` 8.1 ms; the hook before this change 62.3 ms on a /code prompt and 62.7 ms on a plain one; after it 73.0 ms on a /code prompt and 63.1 ms on a plain one. Only a /code prompt pays the transcript read, about 11 ms.

## Result

Tests: `tests/scripts/test_code_context.py` covers the warning over the limit, newest main reply wins and subagent replies are skipped, no warning at the limit, only a typed run start is checked, a new session or a missing transcript stays quiet, and the hook prints the warning on UserPromptSubmit and nothing on another prompt or on Stop. `tests/scripts/test_format_changed.py` still passes unchanged.

## Watch

`code-context-warn-main-cache-read`: main-session cache read per /code turn, expected down.

## Back-out

Revert the commit.
