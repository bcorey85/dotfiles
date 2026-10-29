---
type: "Change"
title: "shell-write-gate follows names to the file a script writes"
description: "Sessions and coders edited tracked files through one-off Python scripts. shell-write-gate already denied an untracked script whose write statement named a tracked file as a literal, but an edit script names its target through a variable, an edit list or edit dict looped over, a helper's parameter, a joined path, or a method `.open(`, so the gate let it through and the edits skipped the Write/Edit hooks. The gate now follows the written target's names through assignments, for loops and function calls, joins path literals, and its deny text says to keep scratch scripts in the scratchpad."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T14:46:21-05:00"}
seq: 182
kind: "fix"
components: ["script/shell-write-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_shell_write_gate.py::ShellWriteGateTest::test_untracked_script_that_writes_a_tracked_file_through_a_name_is_denied"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `shell_write_gate.py`, rule 4 (an untracked, not git-ignored script or inline code that writes a tracked file):
  - Each file write now has a target: the receiver of `.write_text(`/`.write_bytes(`, the receiver and first argument of a method `.open(`, the last argument of a copy, move, rename or perl open, else the first argument of the call.
  - The names in that target are followed up to four hops through assignments, for loop iterables, and, for a function parameter, the arguments of each call of the function.
  - Each bound text gives its string literals and their `/` join as candidates (`ROOT / "docs" / "a.md"`). A candidate that resolves to a tracked file denies the run.
  - Only the target is traced, so a script that reads a tracked file into a name and writes that content elsewhere still passes. A loop over a dict's `.items()` traces the whole dict, keys and values, so a dict that maps output names to tracked sources is denied even when it only reads them; this errs safe.
  - The deny text adds: keep any scratch script in the scratchpad, never in the repo tree.
- Closes the queue item scripted-file-edits-skip-the-write-and-edit-hooks: an edit script that names its target through a variable, edit list, edit dict, helper, joined path or method `.open(` is denied, so scratch edit scripts stop piling up in the repo tree.

## Evidence

- About twenty untracked edit scripts sat in work trees. Their shapes (a path variable, an edit list, a helper, a joined path) all passed the old gate, which read only literals inside the write statement.
- The new test fails before the change on all six shapes (variable, edit list, helper, joined path, method open, edit dict), and read-then-write-elsewhere scripts, including a loop over `zip(` of sources and targets, still pass.

## Result

- The 72 shell-write-gate tests pass, ruff is clean, and the duplicate-code check passes.

## Watch

—

## Back-out

Revert the commit. The gate then reads only literals in the write statement again.
