---
type: "Change"
change_type: "fixed"
title: "shell-write-gate deny names git restore for a git show or cat-file redirect"
description: "A shell-write-gate deny of a redirect fed by `git show <rev>:<path>` or `git cat-file` now names `git restore --source=<rev> -- <path>`."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T09:19:32-06:00"}
seq: 1
kind: "fix"
components: ["script/shell-write-gate"]
evidence: ["shell-write-gate-leaves-no-path-to-restore-a"]
watches: []
test: "tests/scripts/test_shell_write_gate.py::test_a_denied_git_show_or_cat_file_redirect_names_git_restore"
asked: ""
proof: []
unmeasured: ""
---

## Change

When the gate denies a redirect or tee write and a command in the text is `git show` with a `<rev>:<path>` argument or `git cat-file`, the deny ends with: Restore a tracked file from a revision with `git restore --source=<rev> -- <path>`. Both gates already allow that command.

## Evidence

shell-write-gate-leaves-no-path-to-restore-a

## Result

A coder that tries to restore a file through `git show rev:path > path` gets the allowed command in the deny, not only "use Edit or Write".

## Watch

—

## Back-out

Drop `reads_file_from_revision`, `RESTORE_HINT` and the `try` around the target checks in `run`.
