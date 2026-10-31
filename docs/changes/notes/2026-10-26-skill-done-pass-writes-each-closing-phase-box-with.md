---
type: "Change"
change_type: "changed"
title: "skill-done pass writes each closing-phase box with its evidence"
description: "code_step.py skill-done pass now needs one --evidence per open Success Criteria item in a closing phase; it ticks each box and writes a Done line under it, so refactor and test-audit results reach the plan."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T11:19:27-05:00"}
seq: 51
kind: "fix"
components: ["script/code-step", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_skill_done_pass_writes_each_evidence_under_its_box"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step.py skill-done pass` takes `--evidence "<text>"` once per open Success Criteria or Automated Verification
  item in the closing phase. It ticks each box and writes `  - Done: <text>` under it, in one plan write.
- A missing or wrong count stops the run with the count it got and the count it needs, and changes nothing.
- Manual, CI-verified, human-only and N/A items are left alone. A phase with no open items passes as before.
- The closing-phase prompt lists the open items and prints the `skill-done pass` command with one `--evidence` slot
  per item. The `/code` skill runs that printed command. `_shared/closing-phases.md` states the rule.
- `script_utils.pop_repeated_option` reads a repeated flag.

## Evidence

- Judgment from a merged plan where the refactor box ("concentration gate evaluated with both counts stated") and the
  test-audit box ("denominator stated; every finding routed") were both left open at merge, after both skills ran.
- Five new tests fail on the base commit and pass after; the pop_repeated_option test errors before and passes after.

## Result

- Full suite and ruff pass on the worktree.

## Watch

—

## Back-out

Revert the commit. Plans already written keep their `Done:` lines, which are plain markdown.
