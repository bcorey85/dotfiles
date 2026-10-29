---
type: "Change"
change_type: "fixed"
title: "A refactor or review finding can log a file path that holds spaces"
description: "refactor-flow.py log, log-escape and log-review-finding accept a file= value with spaces. All three refuse a file= value that holds a line break, or whitespace followed by name=, which is the shape of a swallowed key=value pair."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T14:48:04-05:00"}
seq: 18
kind: "fix"
components: ["script/refactor-flow", "script/log-escape", "script/log-review-finding"]
evidence: ["work incident", "tests"]
watches: []
---

## Change

- `skills/refactor/scripts/refactor-flow.py`: the check that refused any space in a finding's `file` is replaced. A `file` value can hold spaces. It is refused when it holds a newline or a carriage return, or whitespace followed by `name=`.
- `scripts/log-escape` and `skills/review/log-review-finding`: the `file` key uses the same rule, with the same refusal message. Every other key keeps its old rule: only `desc` (and `result` in log-review-finding) can hold a space.
- `tests/scripts/test_refactor_flow.py`: new tests run each case against both writers and refactor-flow.

## Evidence

Work incident: `refactor-flow.py log` refused a finding whose file path held a space, so the refactor step could not log it.

A code review found that the first staged fix guarded line breaks only in refactor-flow. The writers checked a `file` value only when it held a literal space, so a tab or newline before `name=` passed. Seven other callers use the writers directly. The rule was made the same in all three files before install. The review also found that no log reader splits `file` on spaces.

Trade: a real path such as `docs/notes v=2.md` is refused, because it has the shape of a swallowed pair.

## Result

Staged 2026-10-21 in the fourth script fix batch. 83 tests pass on the staged copies. The new tests fail against the installed scripts. Installed 2026-10-21. The full suite ran 1,481 tests in 39 files. One file failed, on a real plan that the criteria parser refuses, which this batch did not touch.

## Watch

None. No intake metric counts refused log calls.

## Back-out

Restore the previous `refactor-flow.py`, `log-escape`, `log-review-finding` and `test_refactor_flow.py` from the dotfiles history.
