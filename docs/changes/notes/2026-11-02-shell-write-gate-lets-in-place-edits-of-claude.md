---
type: "Change"
change_type: "fixed"
title: "Shell-write gate lets in-place edits of Claude scratch files through"
description: "An in-place edit (sed -i and the like) of a file under the session temp root passes the gate, so read-only agents can finish a probe."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-02T19:31:42-06:00"}
seq: 11
kind: "fix"
components: ["script/shell-write-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_shell_write_gate.py::ShellWriteGateTest::test_in_place_edit_under_claude_temp_root_allowed"
asked: ""
proof: []
unmeasured: "Two architects hit the deny in one run; no intake row counts this deny reason."
---

## Change

`shell_write_gate.py` skips the in-place-editor deny when the edited file resolves, symlinks and `..` followed, to a path inside `/tmp/claude-<uid>/`. `hook_input.py` gains `claude_temp_root` and `is_under_claude_temp_root`. Every other path, including other `/tmp` paths and repo paths, stays denied.

## Evidence

The gate told read-only agents (tools Bash, Read, Glob, Grep, LSP) to use Write or Edit on a scratch file. They have neither tool, so two architects stopped their probe.

## Result

The new test fails against the previous gate, which denied the scratch-file edit. Two further tests show an unrelated `/tmp` file and a `..` escape out of the root still deny.

## Watch

None.

## Back-out

Revert the gate and `hook_input.py` edits.
