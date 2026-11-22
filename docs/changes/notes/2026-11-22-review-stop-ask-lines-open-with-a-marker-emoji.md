---
type: "Change"
change_type: "changed"
title: "Review stop ask lines open with a marker emoji"
description: "Each ask line a review stop shows the user opens with a marker emoji and its number, so the user can tell the asks apart at a glance."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T14:55:12-06:00"}
seq: 22
kind: "user-rule"
components: ["shared/review-fork-run", "skill/review"]
evidence: ["user request"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: "The change is a script output format, not a prompt rule, so the rule meter has no scenario for it. No intake number reads how fast the user scans the asks."
---

## Change

`scripts/review/review_asks.py`, `numbered_ask_lines`: each ask line opens with the orange diamond marker and its number
(`🔶 1. a.py:1  [code-reviewer/smell]`, was `1. a.py:1  [code-reviewer/smell]`). The plain form opens the same way
(`🔶 1. Cap at 3?`). The review fork repeats the lines word for word, so the user sees the marker.

## Evidence

user request: the user asked for emoji to break up the lists they rule on. Searched every script, skill and agent for a
reader of the line: none parses the text back (asks-done takes outcome words by position; packets hold asks as JSON
fields), so a packet saved with the old line form loads unchanged.

## Result

New tests in `tests/scripts/test_review_asks.py` (`NumberedAskLinesTest`) pin the new line in both forms and the load of an
old-form packet. The full suite passes. See `unmeasured`.

## Watch

None: see `unmeasured`.

## Back-out

Remove `ask_line_open` and use `f"{number}."` in `numbered_ask_lines`.

