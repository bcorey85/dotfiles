---
type: "Change"
change_type: "fixed"
title: "Shell-write-gate resolves a script's write under its absolute root"
description: "A script that writes a relative literal joined onto a name bound to one absolute path (`R / 'a'`, `T + f`, `os.path.join(R, 'a')`) is now checked under that path, so scratch probes outside the repo pass; a relative write after a cd stays denied with a message that names the cd."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T10:43:23-05:00"}
seq: 363
kind: "fix"
components: ["script/shell-write-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_shell_write_gate.py::ShellWriteGateTest::test_relative_write_joined_to_an_absolute_root_resolves_under_that_root"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The interpreter-write check finds a write target's root: its first name that is not called and is followed by a
  join (`/`, `+` or `,`). When every binding of that name (assignments, augmented assignments, loops, call
  arguments) holds exactly one string literal, an absolute path, the same in all of them, the relative literals of
  the write's target are joined onto it before the tracked-file check. A name bound to different paths, bound to a
  relative path, or a bare loop name is no root, so those writes are checked against the session cwd as before.
  Relative literals of another write in the same statement are not rerooted.
- A relative path a script writes is checked against the session cwd and each literal cd folder before the step.
  When the command moved with a cd, the deny says the script ran after a cd to that folder and names the relative
  path, with the hint to use an absolute path. Following the cd to allow the write stays out of scope.
- In-place edits (`sed -i` and the rest) are unchanged.

## Evidence

- A bench run showed the gate denying scratch probes that wrote `(R / 'rel')` with `R` a /tmp path: it read the
  relative literal alone and matched a tracked file in the session's repo. Each false block cost a retry.
- The same run showed a script run after `cd /tmp/...` denied with a message naming the session repo's file, which
  sent the agent to the wrong file.

## Result

Against the gate before this change, the absolute-root test is denied: `tracked.txt` resolves under the session
repo. After it, `test_shell_write_gate.py` passes (79 tests), including writes onto a repo root and rebound roots
that stay denied, and ruff passes. A root bound to a join with another name (`R = '/x/' + BASE`) is no root, so
it stays denied. The joined path is normalized before the tracked-file check, so a `..` escape through a missing
folder is denied like one through an existing folder. The test count is unchanged (79) because the new shapes are
cases in the existing denied-roots test.

Known limit: a target that starts with a string literal (`Path('/tmp/x') / 'a'`, `'/tmp/x/' + R`) has no root, so
its relative literal is still checked under the session cwd and each cd folder, as before this change.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit. Scripts that write under an absolute scratch root are again denied when the relative part names
a tracked file in the session repo, and the cd deny names the session file.
