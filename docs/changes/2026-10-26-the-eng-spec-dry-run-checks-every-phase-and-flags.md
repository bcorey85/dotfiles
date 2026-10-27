---
type: "Change"
title: "The eng-spec dry run checks every phase and flags broken count and pgrep criteria"
description: "A new script runs every Automated Verification command of every phase and flags a self-matching pgrep -f and a count that differs from the plan's own code."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-26T00:20:30-05:00"}
seq: 40
kind: "fix"
components: ["script/criteria-dry-run", "skill/eng-spec"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_criteria_dry_run.py::CriteriaDryRunTest::test_runs_the_commands_of_every_phase_not_only_the_first"
asked: ""
proof: []
unmeasured: "A criterion that cannot pass and reaches plan review is not logged as its own number."
---

## Change

Step 16b of the finalize phase now runs `tools/criteria_dry_run.py <spec.md>` once. It parses the plan with `plan_format`, runs the command of every Automated Verification item in every phase, and prints RED, GREEN or BROKEN for each. It adds a FLAG for a `pgrep -f` whose pattern the shell running the check also contains, and for a count criterion (`rg -c`, `grep -c`, `| wc -l`) whose stated number differs from the number of matching lines in the phase's own code blocks.

## Evidence

judgment: a dry run of one phase let two criteria that could never pass reach plan review, where they were found by luck. Tests: `test_flags_a_pgrep_pattern_that_matches_the_shell_running_the_check`, `test_flags_a_count_that_differs_from_the_count_in_the_plans_code`. All fail on the base commit, where the script does not exist.

## Result

Scoped tests and ruff pass.

## Watch

—

## Back-out

Delete `tools/criteria_dry_run.py` and its test, and restore the old step 16b text.
