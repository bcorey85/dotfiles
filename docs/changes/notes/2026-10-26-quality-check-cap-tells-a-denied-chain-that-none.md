---
type: "Change"
change_type: "changed"
title: "quality-check-cap tells a denied chain that none of its other steps ran"
description: "When the repeat-check cap denies a multi-step Bash call, the deny text says the whole call was refused for that fragment alone and to send the other steps again as their own call."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:41:50-05:00"}
seq: 98
kind: "fix"
components: ["script/quality-check-cap"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_quality_check_cap.py::QualityCheckCapTest::test_a_denied_chain_names_the_matched_fragment_and_says_the_other_steps_run_as_their_own_call"
asked: ""
proof: []
unmeasured: ""
---

## Change

- A deny on a command with more than one step appends: none of its other steps ran; send them again without the
  denied fragment, as their own call. A single-step deny keeps its old text.
- New tests pin that a lone check gets no chain advice, and that a subagent which edits after the main thread's run
  may run the check once before the cap applies.

## Evidence

- A coder chained a build, a format and a repeat test run in one call; the cap denied the whole call and the coder
  redid the other steps blind, not knowing they had not run.
- The named test fails on the base gate and passes after.

## Result

- See the branch's suite run. The separate report that the cap refuses a subagent's run after its own edit did not
  reproduce: the cap already keys runs per agent, so that cause stays open.

## Watch

—

## Back-out

Revert the commit.
