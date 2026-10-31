---
type: "Change"
change_type: "fixed"
title: "The main-branch guard in the bash safety hook reads only each push command's own arguments"
description: "The main-branch guard no longer denies a chained command that holds push and a main or master word in different commands."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-25T22:39:01-05:00"}
seq: 26
kind: "fix"
components: ["script/bash-safety-gate", "script/git-push-main-check"]
evidence: ["repro"]
watches: []
test: "tests/scripts/test_bash_safety_gate_push_main.py::GitPushMainRuleTest::test_pushes_to_other_branches_are_allowed_beside_a_main_word"
asked: ""
proof: []
unmeasured: ""
---

## Change

The main-branch guard in bash-safety-gate.sh looked for a push word and a main or master word anywhere in the command. It now runs tools/git_push_main_check.py, which splits the command with lib/shell_command.py and reads only the arguments of each push command. It still denies main, master, HEAD:main, +master and refs/heads/main targets. A command the parser cannot read falls back to the old text match. The generator for this file is not on this machine, so the edit was made in place; carry it into the generator.

## Evidence

Two real false blocks on 2026-10-25: a worktree add from origin/master chained before a branch push, and a queue update naming a main-turns slug chained before a push of bench-base. Both now pass; the test covers them and every deny case.

## Result

One call instead of two for a chained push beside a main word.

## Watch

None: the hook block log shows the rule by reason tag.

## Back-out

Restore the grep line in bash-safety-gate.sh and delete tools/git_push_main_check.py.

