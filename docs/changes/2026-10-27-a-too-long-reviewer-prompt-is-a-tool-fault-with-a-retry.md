---
type: "Change"
title: "A too-long reviewer prompt is a tool fault with a retry"
description: "The review loop script passes the round-one fix diff as a file path, marks a crashed run `tool_fault`, and /code stops on it with a review-again route instead of a critical blocker."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T23:59:00-05:00"}
seq: 138
kind: "fix"
components: ["script/review-loop", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_crashed_review_call_stops_as_a_tool_fault_not_as_a_blocker"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_loop_script` writes the round-one fix diff to `round<N>-fix.diff` in its state folder. The second
  reviewer's prompt names that path in place of the inlined diff.
- A script crash adds a `tool_fault: <reason>` line to the packet. `handback` reads it as an optional scalar key.
- `code_step` stops on a packet with `tool_fault` as `stopReason: tool-fault`: the review did not finish, it found
  nothing, and `review-again` runs it again. `review-again` accepts that stop.

## Evidence

- A second code-reviewer call returned "Prompt is too long". /code reported a critical blocker, and review-again
  refused the stop.
- The new tests fail on the old scripts.

## Result

- A large round-one fix diff no longer runs the reviewer prompt past its limit.
- A crashed review call ends in a tool-fault stop that review-again retries.

## Watch

—

## Back-out

Revert the commit.
