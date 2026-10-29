---
type: "Change"
change_type: "fixed"
title: "The scripted-edit trace strips comments before it reads a literal"
description: "shell-write-gate now strips # comments, following quote state, before any tracing, and splits a dict literal at its top-level colon, so a read-only loop over .items() that writes elsewhere is no longer denied. Before, a ')' or a quote inside a # comment in a list or dict literal cut the trace short, so a write to a tracked file passed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T20:51:47-05:00"}
seq: 218
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

- `lib/code_text.py` gains `without_comments`: it cuts each `#` comment from its line. A `#` counts only outside quotes, at line start or after whitespace or one of `,([{:;`, so perl `$#x`, JS `.#x` and a `#` inside a string such as `'docs/#notes.md'` stay.
- `shell_write_gate.py` traces the script twice, as written and with comments stripped, and denies when either names a tracked file. So a `#` that starts no comment (a JS regex, perl `s/a #b/`) cannot hide a write on its line.
- `tuple_fields` now finds the first top-level bracket, and splits a dict literal's `key: value` elements at the first top-level colon, so a loop target picks the side at its position.
- A loop over `NAME.items()` follows `NAME`'s assignment.
- Closes the queue item the-scripted-edit-trace-denies-read-only-use-of-a.

## Evidence

- A probe showed a list literal with `# step 1)` inside let a write to a tracked file pass.
- Before the fix, the two comment-with-paren deny cases and the two `.items()` allow cases fail.

## Result

- The 76 shell-write-gate tests pass, ruff is clean, and the duplicate-code check passes.

## Watch

—

## Back-out

Revert the commit.
