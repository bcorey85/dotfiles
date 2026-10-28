---
type: "Change"
title: "shell-write-gate: /var/tmp counts as a temp dir"
description: "A coder's redirect into a new log under /var/tmp was denied as a new file outside a temp dir unless $TMPDIR named /var/tmp; /var/tmp now always counts, and a redirect onto a git-tracked file there still denies."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T14:17:15-05:00"}
seq: 195
kind: "fix"
components: ["script/shell-write-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_shell_write_gate.py::ShellWriteGateTest::test_a_coder_may_redirect_into_a_new_log_under_var_tmp_but_not_onto_a_tracked_file_there"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `hook_input.temp_roots` lists /var/tmp beside /tmp, the system temp dir and $TMPDIR.
- The tracked-file check runs before the temp check, so a redirect onto a tracked file inside a work tree under
  /var/tmp still denies.
- The gate tests build their outside dir under the real home, since /var/tmp is no longer outside.

## Evidence

- A coder's `cargo clippy > /var/tmp/<repo>/clippy.log` was denied as a new file outside a temp dir.

## Result

- A coder can write a new log under /var/tmp.

## Watch

—

## Back-out

Revert the commit.
