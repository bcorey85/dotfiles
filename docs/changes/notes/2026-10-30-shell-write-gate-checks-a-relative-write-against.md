---
type: "Change"
change_type: "fixed"
title: "Shell write gate checks a relative write against each cd folder before it"
description: "A shell write onto a tracked file in the folder a cd moved to is denied, where before only the session cwd was checked and `cd sub && printf x > tracked.md` went through."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T08:17:22-05:00"}
seq: 337
kind: "fix"
components: ["script/shell-write-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_shell_write_gate.py::ShellWriteGateTest::test_a_relative_target_is_checked_against_each_literal_cd_folder_before_it"
asked: ""
proof: []
unmeasured: ""
---

## Change

- A relative redirect or tee target is checked against the session cwd and against each folder a literal `cd` or
  `pushd` moved to before it, each resolved against the one before. A tracked file under any of them denies.
- A relative target after a `cd`, `pushd` or `popd` whose folder is not a literal (a `$`, a substitution, a glob,
  `cd -`, `~user`, a directory-stack index, a bare `pushd`, any `popd`) is denied. `$TMPDIR` and `$HOME` in a cd
  folder are expanded first, as they are in a write target.
- `shell_command.cd_folder` reads a `cd` or `pushd` folder word.
- In a coder, any relative target after a folder change is denied. Before, the coder's new-file rule skipped it.
- The change only adds denies: every command the gate denied before is still denied.

## Evidence

- Read of the gate: it resolved a relative target against the session cwd only, so a write onto a tracked file in the
  folder a `cd` moved to was allowed. An architect read on 2026-10-29 set the deny-only shape, which keeps clear of
  the follow-the-cd rule dropped on 2026-10-27 for opening deny-to-allow holes.

## Result

Against the gate before this change, the two new tests fail (a tracked file in a cd folder and a folder that is not a
literal were allowed) and the rewritten coder test fails (a coder's relative write after a cd was allowed). After it, `test_shell_write_gate.py` passes (74
tests) and ruff passes.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit. Relative shell writes after a `cd` are then checked against the session cwd only.
