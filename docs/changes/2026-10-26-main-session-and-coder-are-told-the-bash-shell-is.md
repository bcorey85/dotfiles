---
type: "Change"
change_type: "changed"
title: "Main session and coder are told the Bash shell is zsh"
description: "The orchestration rule and coder-core say an unquoted $VAR stays one word under zsh and splits under bash, and to loop over an array in a form both shells read, or write each command out."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:39:43-05:00"}
seq: 95
kind: "fix"
components: ["rule/orchestration", "skill/coder-core"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_the_main_session_and_the_coder_loop_over_arrays_in_a_form_zsh_and_bash_both_split"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `orchestration.md` Tools: an unquoted `$VAR` holding spaces stays one word in zsh and splits in bash; loop over an
  array with `for f in "${files[@]}"`, which both shells read the same way, or write each command out, and never keep
  a command prefix or file list in a plain string variable.
- `coder-core` hook-block list: the same rule as one bullet, with the two failing shapes (`$N cargo test`, `git add $F`).

## Evidence

- One session misfired four times on this: the orchestrator's `git add $F` hit one joined path (exit 128), and three
  coders lost runs to a `$O` env prefix, a `$N` nice prefix (exit 127) and a `$t` test-name loop (7 usage errors and
  a read of stale logs).
- The test pins the rule text in both files; it fails on the base tree.

## Result

- See the branch's suite run.

## Watch

—

## Back-out

Revert the commit.
