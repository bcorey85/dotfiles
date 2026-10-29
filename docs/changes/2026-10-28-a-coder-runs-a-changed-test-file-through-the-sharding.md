---
type: "Change"
title: "A coder runs a changed test file through the sharding runner"
description: "The toolkit script rules now tell a coder to run a changed test file through tests/parallel_tests.py, which splits test_code_step.py into four processes, so the file finishes inside one 600 s tool call."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T20:05:00-05:00"}
seq: 215
kind: "fix"
components: ["rule/toolkit-script-rules"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_a_coder_runs_a_changed_test_file_through_the_sharding_runner"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `docs/toolkit-script-rules.md`, Tests section: one new bullet. Run a changed test file through `python3 tests/parallel_tests.py <test file name>`, never through `python3 -m unittest` alone.
- Closes the queue item code-step-test-file-runs-past-the-tool-timeout.

## Evidence

- `python3 -m unittest test_code_step` ran 562 tests in 755 s on a loaded 8-core machine. No single test dominates: the slowest took 19 s, and most take about 1 s, each starting several code_step.py processes.
- `python3 tests/parallel_tests.py test_code_step.py` ran the same 562 tests in 248 s wall-clock, through the four shards `SHARDS` already names.

## Result

- The rule is in the file the repo's CLAUDE.md loads into every session. The new guidance test fails without the bullet and passes with it.

## Watch

—

## Back-out

Revert the commit. A coder then runs test_code_step.py as one process again and hits the tool timeout.
