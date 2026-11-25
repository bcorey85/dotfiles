---
type: "Change"
change_type: "fixed"
title: "code run script names and script call arguments get one owner"
description: "The /code review script names and a reader for a script's call arguments move to one owner each in lib, with no behavior change."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T14:07:29-06:00"}
seq: 3
kind: "fix"
components: ["script/coder-gate", "script/code-wait", "script/fork-children"]
evidence: ["incident"]
watches: []
test: "tests/scripts/test_shell_command_words.py::ScriptCallArgumentsTest::test_the_words_after_the_script_are_returned"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

New `lib/code_run_names.py` owns the phase start, review start and wait script names and the wait agent and review verbs. New `lib/shell_command_words.py` `script_call_arguments` returns the words after a script's own word. coder_gate, code_wait, code_review_start and fork_children read them.

## Evidence

A /code fork ended after a coder dispatch with no review; the gate that catches it runs outside review/ and needs these names without loading it.

## Result

No behavior change; the existing coder_gate, code_wait and fork_children tests pass.

## Watch

None.

## Back-out

Revert the commit.
