---
type: "Change"
title: "A repo with no check found is reviewed, and the hand-back says no full check ran"
description: "When neither CLAUDE.md nor the check finder names a full check, the review loop runs its review with the coder's scoped tests standing as the check, and the packet's full_check says so, in place of a critical-blocker stop that a restart only repeats."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T23:59:00-05:00"}
seq: 139
kind: "fix"
components: ["script/review-loop-script", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_repo_with_no_check_found_is_reviewed_and_its_packet_says_no_full_check_ran"
asked: "2026-10-27: agent-evals-64 assigned queue item review-loop-stops-dead-in-a-repo-that-names-no"
proof: []
unmeasured: ""
---

## Change

- `review_loop_script.check_command_for`: a check-finder reply that names no command returns None and prints the
  finder's reason on stderr. It no longer raises. A reply with no JSON object still raises.
- `full_check.run` with no command returns `not run (no check found; the coder's scoped tests stand)`. The hand-back
  renders it as its `Full check:` line.
- `review-loop.md` Step 6 and the packet's `full_check` values name the same result for the agent loop.

## Evidence

- In a repo with no Makefile, package.json, CI file or `Quality check:` line, /code stopped before review with a
  ValueError and pointed at a restart that hit the same stop.
- The changed test fails on the old script.

## Result

- The review runs and converges. The packet's `full_check` says no full check ran.

## Watch

—

## Back-out

Revert the commit.
