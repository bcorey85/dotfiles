---
type: "Change"
title: "A finding on a scoped package path keeps its at sign"
description: "The review loop reads a finding's file:line with the same path regex as the hand-back, so a finding on a path like @scope/pkg/file.ts keeps its @ and routes and matches by its real path."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T22:30:00-05:00"}
seq: 260
kind: "fix"
components: ["script/review-loop-script", "script/script-utils"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_finding_on_a_scoped_package_path_keeps_its_at_sign"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `script_utils.PATH_TEXT`: the one path pattern. `PATH_LINE` and `FILE_NAME` are built from it.
- `finding_record.parse_finding`: reads the file:line through `script_utils.PATH_LINE` and `split_location`, and takes it out of the title with the same regex. `FINDING_FILE` is gone.

## Evidence

- A complexity and smell review found that `FINDING_FILE` had no `@` in its path class. A finding on `@scope/pkg/file.ts:12` lost its `@`, so `parse_finding` and the hand-back named two different paths.

## Result

- On the base script, the new test in `test_review_loop_script.py` fails. With this change it passes.

## Watch

—

## Back-out

Revert the commit. A finding on an `@scope/` path loses its `@` again.
