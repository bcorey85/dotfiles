---
type: "Change"
change_type: "fixed"
title: "test-reviewer reads files in place, and the review packet names each blocked agent"
description: "test-reviewer never copies the tree into a scratchpad and reports a refused call on a `Blocked:` line; review-loop carries it in a `blocked_agents` packet field, which handback renders under its own heading."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T15:00:00-05:00"}
seq: 169
kind: "fix"
components: ["agent/test-reviewer", "agent/review-loop", "script/handback"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::RenderTest::test_a_blocked_agent_and_the_step_it_skipped_print_under_their_own_heading"
asked: ""
proof: []
unmeasured: ""
---

## Change

- test-reviewer reads every file in place and never copies the tree or a file into a scratchpad. When a hook or
  permission refuses a call, it skips that step and opens its report with `Blocked: <call> — <step skipped>`.
- review-loop's packet gains `blocked_agents`, one `- <agent>: <step it skipped> (<the refused call>)` line per entry.
- handback reads `blocked_agents` as an optional list and renders it under `### Blocked agents (not reviewed)`, so
  /review and /code both show it.
- The opencode ports of both agents carry the same lines.

## Evidence

- In a /review loop, test-reviewer piped `git ls-files` into a bulk `cp`. The credential hook denied it, the slice
  halted, and the packet did not say which agent was blocked or which step it skipped.
- The new test fails on the old handback.

## Result

- A review with a refused reviewer step says which agent and step, so the caller can judge coverage.

## Watch

—

## Back-out

Revert the commit.
