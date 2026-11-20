---
type: "Change"
change_type: "fixed"
title: "The shell-write gate reads a perl flag cluster with a digit as an in-place edit"
description: "`perl -0pi` on a tracked file is denied as an in-place edit; the flag check read only letters, so a cluster with `-0` passed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-17T19:33:21-06:00"}
seq: 1
kind: "fix"
components: ["script/shell-write-gate"]
evidence: ["census", "tests"]
watches: []
test: "tests/scripts/test_shell_write_gate.py::ShellWriteGateTest::test_a_perl_flag_cluster_with_a_digit_is_an_in_place_edit"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/inplace_edit.py` reads a flag cluster with digits (`-0pi`, `-0777pi`) as carrying `-i`, and the gate's
PRECHECK pattern builds on the same `inplace_edit.PERL_I_FLAG`, so it takes digits in a cluster too. A coder or main
session running `perl -0pi -e ... tracked.txt` is denied `[inplace_edit]`, as `perl -pi` already was.

## Evidence

Queue item `shell-write-gate-lets-perl-0pi-and-a-zsh-brace-or`. A replay of real local transcripts (382,172 distinct
Bash commands) found 76 `perl -0pi` checks that the old gate allowed: 38 as the main session, 38 as a coder.

## Result

The new test fails on master's gate (the command is allowed) and passes now. In the replay those 76 checks moved
allow to deny `[inplace_edit]`; 10 more were already denied for another reason and now name `[inplace_edit]`. No
other in-place verdict changed.

## Watch

None.

## Back-out

Revert the digit in `PERL_I_FLAG` in `lib/inplace_edit.py`.
