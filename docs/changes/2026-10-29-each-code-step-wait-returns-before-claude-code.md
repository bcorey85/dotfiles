---
type: "Change"
title: "Each code-step wait returns before Claude Code moves the fork's call to the background"
description: "A code-step verb that waits on an agent now prints its wait line within 150 seconds (was 570), before Claude Code moves the fork's Bash call to the background at 180 seconds, so the fork reads the line and runs the verb again instead of stalling on an empty background call. The cap still stops a silent agent after about thirty minutes."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T16:52:26-05:00"}
seq: 277
kind: "fix"
components: ["script/code-step"]
evidence: ["transcript read", "tests"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_resume_with_no_row_returns_before_claude_code_moves_the_call_to_the_background"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code/code_step_core.py`: one wait for an agent's hand-back now lasts at most 150 seconds (570 → 150), and the cap
that stops the run is twelve waits instead of three, so a silent agent still stops the run after about thirty minutes
(1710 → 1800 seconds). Every verb that waits on an agent uses this wait: `resume` after a coder or review dispatch, and
the review waits in `code_step_review.py`. Each prints its `ACTION: wait` line, and the fork runs the same command
again, as before.

## Evidence

A bench transcript read. Claude Code moves a subagent's Bash call to the background once it has run 180 seconds,
whatever Bash timeout the call asks for. A main session can raise that limit; a subagent cannot. The /code fork's
570-second `resume` passed it. The fork then read an empty output, its second `resume` was refused while the first
still held the verb lock, the Stop hook kept the fork from ending, and the main session spent a turn on the fork's
"waiting on its own background work" notice. In the run read, this happened twice. It cost one main-session Opus
response (134,718 cache-read tokens) and twelve Sonnet fork responses (403,913 cache-read, 7,248 cache-write and 1,829
output tokens).

## Result

The new test runs `resume` with the script's own wait on a fast clock. Before the change it printed its wait line
after 570 seconds; after it, after 150 seconds. A second test,
`test_the_script_s_own_waits_reach_the_cap_stop_only_after_25_minutes`, holds the cap at about thirty minutes of waits.
The code-step suite passes.

The trade: a long wait now takes one Sonnet fork response per 150 seconds instead of per 570, about 30,000 cache-read
tokens each. A twenty-minute review loop takes eight `resume` calls instead of three, and none of them stalls.

Not covered: a verb that runs a long command itself, such as `tick` running a phase's whole-suite checks, can still
pass 180 seconds.

## Watch

None. The intake does not count Bash calls that Claude Code moved to the background; the new test holds the limit.

## Back-out

Set `HANDBACK_WAIT_SECONDS` back to 570 and `HANDBACK_TOTAL_WAIT_MULTIPLE` back to 3, and delete the two tests.
