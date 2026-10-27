---
type: "Change"
title: "code_step.py is split by concern into seven modules"
description: "code_step.py drops from 2312 to 605 lines: the start, review, gate and report concerns move into their own modules with each function's text unchanged, so the scripted review loop can be wired in under the toolkit's 1000-line rule."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:41:24-05:00"}
seq: 72
kind: "structured"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: ""
asked: ""
proof: ["2026-10-26-scripted-review-loop-with-bounded-re-review-vs"]
unmeasured: "A move with no behavior change; the edit watches ship with the change that wires in the scripted review loop."
---

## Change

- `code/code_step.py` keeps the verb table and dispatch; new modules `code_step_start.py`, `code_step_review.py`,
  `code_step_gates.py` and `code_step_report.py` hold the start, review and asks, gate, and report concerns.
  `take_handback` moves to `code_step_core.py` beside `awaited_handback`.
- Tests repoint import and patch targets; one `CODE_STEP_MODULES` tuple in `tests/scripts/toolkit_paths.py` replaces
  three hand-written module lists. `tests/run.sh` and `ruff.toml` name the new files.

## Evidence

- Step one of the build the finding orders (REPLACE: /code drives the review loop as a script). The toolkit script
  rules forbid a new route or state field in a script over 1000 lines; `code_step.py` was 2312.
- Three AST comparisons found every top-level def of the old file once, with identical text, across the modules.

## Result

- `bash tests/run.sh`: 2380 tests in 72 files, 0 failed. `ruff check` passes. Review converged in two rounds.

## Watch

—

## Back-out

Revert the commit.
