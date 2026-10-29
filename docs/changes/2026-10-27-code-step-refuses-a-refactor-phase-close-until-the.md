---
type: "Change"
change_type: "changed"
title: "code-step refuses a refactor phase close until the concentration gate is evaluated"
description: "A /code refactor closing phase could close with `skill-done pass` and no sign the concentration gate was checked. code-step now counts the added lines itself, prints whether the gate triggers, and refuses the close of a triggered gate until a simplify run is named for the module it computed. The record is saved in the plan."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T16:43:21-05:00"}
seq: 119
kind: "fix"
components: ["script/code-step", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_refactor_skill_done_pass_refuses_a_triggered_gate_with_no_simplify_record"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `code_step_concentration.py` and `lib/numstat.py`: on a refactor closing phase, code-step reads
  `git diff --numstat --no-renames <base>...HEAD`, with the base from `tools/branch-base` or `--base <ref>`. It counts
  added lines per module (a file's folder) and on the branch, skipping lockfiles, generated and test-only files. The
  gate triggers at 100 added lines in the largest module or 300 on the branch.
- The refactor phase prompt prints both counts and whether the gate triggers. When it does, the printed pass command
  carries `--simplify "<module>; <trigger>"`.
- `skill-done pass` on a triggered gate refuses with no `--simplify`, with a malformed one, or with one naming a module
  other than the computed one, and names what is missing. With no base found, it refuses and names `--base`.
- `skill-done pass --simplify` on a phase with no open concentration-gate item (including no open items) is refused,
  writes nothing and leaves the phase open. On a triggered gate the stop names the criterion line to add to the
  phase's Success Criteria (`- [ ] Concentration gate evaluated (module dispatched with the trigger named, or both
  counts stated)`) and the same `skill-done pass` command to rerun, with one `--evidence` per open item including the
  new one. On a gate that did not trigger, the stop says to run `skill-done pass` without `--simplify`.
- An accepted `--simplify` is written into the plan under the concentration-gate criterion as
  `simplify <module> (<trigger>)`.
- New `lib/source_paths.py` holds the lockfile and test-path rules, shared with `code_step_review.py`.
- The review's small-follow-up count (`code_step_review.py` `is_counted_source`) now also skips files under a `dist/`
  folder, since `lib/source_paths.py` adds that rule.

## Evidence

- A /code run closed a refactor phase with a bare `skill-done pass` after a smell sweep. code-step marked the phase done
  and offered auto-advance, though the largest module was well over the trigger and no simplify run or count was given.
  The orchestrator caught it only by reading the report.
- The new refusal test fails before the change: the bare pass closed the phase.

## Result

- The full suite passes: 3180 tests in 87 files, 0 failed. Ruff is clean on the changed files.
- A checkout on master or main with no remote now has no base; the gate refuses until `--base` is passed.

## Watch

—

## Back-out

Revert the commit. Refactor phases close on a bare `skill-done pass` again.
