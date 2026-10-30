---
type: "Change"
change_type: "fixed"
title: "shell-write-gate lets a script read a tracked file passed as an argument"
description: "An untracked script that writes only its own files can now take a tracked file as an argument; a script whose write target comes from argv is still denied."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T14:05:09-05:00"}
seq: 386
kind: "fix"
components: ["script/shell-write-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_shell_write_gate.py::ShellWriteGateTest::test_untracked_script_that_reads_a_tracked_argument_and_writes_its_own_file_passes"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The interpreter-write check counts a script's arguments as written targets only when a write can reach argv: the
  write statement, or a text bound to its target through MAX_NAME_HOPS bindings, mentions `argv`, `ARGV`, `ARGF`,
  perl's `shift`, `parse_args`, `parse_known_args`, `parseArgs`, `Deno.args` or `fileinput`; or the code imports
  click, typer or fire, which bind argv to parameters with no visible call.
- The argv trace also follows unpacking assignments (`src, dst = sys.argv[1:3]`, `my ($out) = @ARGV;`,
  `const [, , out] = process.argv`), which the literal tracer does not read.
- A script with any file write and no argv reach is checked only against the literals its writes name, as before.

## Evidence

- A bench run's session started a helper script with a tracked plan file as an argument. The script read the plan
  and wrote only a pid file and a log under `.git/`. The gate denied it twice because the plan was tracked and the
  script had some write, the review never ran, and the session asked the user to run it by hand.

## Result

Against the gate before this change, the new pass test is denied. After it, `test_shell_write_gate.py` passes (81
tests), including a new test that six argv-target shapes stay denied: Python unpacking, argparse, a `main(argv)`
parameter, `fileinput` in-place, perl `@ARGV` unpacking and node `process.argv` destructuring. Ruff passes.

Known limit: a write target bound in a way the tracer does not read (an attribute set elsewhere, a value returned
from a helper that reads argv) and a parser other than those named is no longer denied when its tracked file comes
in as an argument.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit. Any untracked script with a file write is again denied whenever a tracked file is among its
arguments.
