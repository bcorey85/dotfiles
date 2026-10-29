---
type: "Change"
change_type: "fixed"
title: "code-step reads a start argument with whitespace as task text"
description: "`start` no longer treats a word with whitespace as a plan path, unless that word is an existing file. Task text that names a file path now starts a task run."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-22T09:51:55-05:00"}
seq: 9
kind: "fix"
components: ["script/code-step", "script/script-utils"]
evidence: ["work incident"]
watches: []
---

## Change

- `scripts/code-step.py`, `looks_like_plan_argument`: a word with whitespace is task text, unless the word is itself a file (a real plan whose path has a space).
- `scripts/script_utils.py`: new `has_whitespace(text)`.
- Tests: `tests/scripts/test_code_step.py` checks a task text that names files, both as `--task` text and as a positional argument.

## Evidence

- Work incident: `start --task "Close gap X: add rules in registry/rules/x.toml, add cases in src/x.rs, …"` failed with "no plan file is at …". Any argument with a `/` read as a plan path.

## Result

Task text that mentions file paths starts a task run.

## Watch

None. The intake does not count `start` failures.

## Back-out

Remove the `has_whitespace` check from `looks_like_plan_argument`.
