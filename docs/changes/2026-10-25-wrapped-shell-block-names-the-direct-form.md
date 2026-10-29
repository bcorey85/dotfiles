---
type: "Change"
change_type: "fixed"
title: "Wrapped shell block names the direct form"
description: "The deny text for a wrapped shell command now tells the agent to run the inner command directly as its own Bash call."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-25T22:40:00-05:00"}
seq: 25
kind: "fix"
components: ["script/bash-safety-gate"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_block_next_steps.py::BlockNextStepTest::test_the_wrapped_shell_block_names_the_direct_form"
asked: ""
proof: []
unmeasured: ""
---

## Change

The indirect-shell deny text now ends with: run the inner command directly as its own Bash call, without the shell wrapper, and keep going. The block is unchanged: a wrapped command is still denied. A rewrite of the wrapped command to the inner one was dropped, because an allow decision would skip the auto mode classifier for a command that an unwrapped call never gets past.

## Evidence

census: indirect shell was 22 main blocks and 153 subagent blocks in the newest intake. The old text named no direct form, so agents retried other wrapped forms.

## Result

Effect unmeasured until the next intake; the hook-block-list-cut watch already reads indirect_shell blocks per day.

## Watch

—

## Back-out

restore the old deny text of the indirect-shell rule
