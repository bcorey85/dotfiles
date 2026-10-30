---
type: "Change"
change_type: "changed"
title: "The code-step state store moves out of code_step_core.py"
description: "code_step_core.py drops from 1525 to 1300 lines: the state file, the verb transaction and the session's repo list move to code_step_store.py with no behavior change, so the next code-step change has less to split first."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T12:25:05-05:00"}
seq: 384
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_module_size.py::CodeStepModuleSizeTest::test_the_state_store_is_its_own_module_that_never_imports_code_step_core"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step_store.py` now holds the state folder and file, load, save and drop, the abort archive reader, the verb transaction and the session's repo list. Each function's text is unchanged, except `verb_transaction` (now `state_transaction` in the store, which takes the report callback) and `finish_verb` (takes that callback).
- `code_step_core.verb_transaction` calls `code_step_store.state_transaction` with the function that prints the stop for a state file that changed under the verb. Imports run one way, so the store cannot call `emit`.
- A caller imports a name from the store when `code_step_core` no longer uses it. Names that core still uses stay importable from core.

## Evidence

- `code_step_core.py` was over the 1000-line size rule, and the state store is one concern.

## Result

- The new test fails before the change: `code_step_store.py` does not exist. It passes after.
- The code-step test modules pass and ruff passes. `code_step_core.py` is 1300 lines, still over the rule, so a verb or state field needs one more split first.

## Watch

- None: a move with no behavior change has no number to read.

## Back-out

- Revert the commit.
