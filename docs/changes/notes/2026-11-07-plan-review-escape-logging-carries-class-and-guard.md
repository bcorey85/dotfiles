---
type: "Change"
change_type: "fixed"
title: "Plan-review escape logging carries class and guard so every row logs"
description: "Each plan-review BLOCKER or GAP now logs on the first call, where before every call was refused."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-07T16:35:53-06:00"}
seq: 11
kind: "fix"
components: ["skill/eng-spec"]
evidence: ["incident"]
watches: []
test: "tests/scripts/test_log_escape.py::LogEscapeTest::test_every_prompt_template_passes_check"
asked: ""
proof: []
unmeasured: ""
---

## Change

eng-spec phase 6b step 20b now gives a full `log-escape` command with `class=` and `guard=` (`check` when a finalization command would catch the defect, else `none`, per the escape ratchet), plus `severity=` and `desc=`. Before, it named only `stage_found`, `gate_missed` and `miss_reason`, and log-escape refuses any row without `class=` and `guard=`. A sweep of every other `log-escape` template in skills, agents and commands found them all complete.

## Evidence

At work, one session's plan-review escape logs were refused three times in a row, and the rows were never written.

## Result

A new test fills each `log-escape` template in the prompt files with its first option and runs `log-escape --check` on it. It fails on the old step 20b (`class= is required`) and passes with the new one; the log-escape test file passes 29 of 29.

## Watch

None: the plan-review rows in `review-escapes.jsonl` (`stage_found` `plan-review`) start appearing, but no watch is needed for a refusal fix.

## Back-out

Revert this commit; step 20b goes back to the template that log-escape refuses.
