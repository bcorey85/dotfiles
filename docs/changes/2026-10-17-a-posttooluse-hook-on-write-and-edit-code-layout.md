---
type: "Change"
title: "A PostToolUse hook on Write and Edit, `code_layout_gate.py`, blocked new Python"
description: "A PostToolUse hook on Write and Edit, `code_layout_gate.py`, blocked new Python, TypeScript or JavaScript code that passed a call result straight into a call that was itself an argument, or that ran more than 8 statements in one block with no blank line."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-17T00:00:00-05:00"}
seq: 3
components: ["rule/settings-json"]
evidence: ["calibration", "judgment"]
watches: []
---

## Change

A PostToolUse hook on Write and Edit, `code_layout_gate.py`, blocked new Python, TypeScript or JavaScript code that passed a call result straight into a call that was itself an argument, or that ran more than 8 statements in one block with no blank line. Added and removed the same day. The `settings.json` entry is gone. The script stays in `~/.claude/scripts/`, unused

## Evidence

calibration, judgment

## Result

Removed. It rejected a test with 10 `expect` lines in a row. A list of like calls (assertions, route setup, seed rows) is readable and would trip it on every write. YAML and SQL inside a query call did not trip it. Calibration before removal: 54 of 1,000 Python stdlib functions and 16 of 1,000 npm functions at 8 statements. It added 29 ms per Python write and 185 ms per TypeScript write, up to 2.4 s under load. The work-intake step that measured it is also removed. The CLAUDE.md layout rule stays as prompt text only

## Watch

—

## Back-out

—
