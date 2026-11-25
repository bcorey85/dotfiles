---
type: "Change"
change_type: "fixed"
title: "Review loop reads finding paths that hold dollar and plus signs"
description: "A finding on a path such as src/routes/$id.test.tsx or src/routes/+page.svelte now parses to that path and reaches the coder."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T14:01:36-06:00"}
seq: 3
kind: "fix"
components: ["script/script-utils", "script/plan-format"]
evidence: ["tests/scripts/test_review_loop_findings.py", "tests/scripts/test_script_utils.py", "tests/scripts/test_plan_format.py"]
watches: []
test: "tests/scripts/test_review_loop_findings.py::FindingLocationTest::test_a_path_with_a_dollar_or_plus_parses_whole_and_its_file_is_kept_by_the_intake"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

script_utils.py gains PATH_NAME_CHARS (`$` and `+` included) and builds PATH_CHARS and PATH_TOKEN_END from it, so every path regex built on them reads such paths whole. PATH_TOKEN_START and the plain (non-token) boundaries of names_path are built from PATH_CHARS too, so `@` now joins the token boundaries. plan_format.py builds PATH_IN_BACKTICKS from PATH_CHARS and PLAN_CHANGE_MARK from PATH_TEXT instead of hand-written sets, so `@` now joins PLAN_CHANGE_MARK as well.

## Evidence

All six new tests fail before the change and pass after:
- `FindingLocationTest.test_a_path_with_a_dollar_or_plus_...`: the old regex cut the path at the `$` or `+`, e.g. `postId.test.tsx`, so the finding had no location or named a file not in the tree.
- `PathCharsTest`: PATH_CHARS lacked `$` and `+`.
- `PathPatternsTest`: BARE_PATH, DOT_SLASH_PATH and LOCATION_ALONE cut a `$` or `+` path short, because PATH_CHARS lacked those characters.
- `NamesPathSigilTest`: a root file counted as named inside `$id.ts`.
- `PlanFormatPathCharsTest` (`test_plan_regexes_read_dollar_and_plus_paths`, `test_a_file_entry_on_a_dollar_path_names_that_path`): PATH_IN_BACKTICKS already read `+` but not `$`, and PLAN_CHANGE_MARK read neither, so a `**File**:` entry on a `$` path was missed and a `+` or `$` path before `PLAN-IMPACT` did not mark a plan change.

## Result

A finding on a `$` or `+` path keeps its path and line and is not skipped as absent from the tree.

## Watch

None.

## Back-out

Revert the commit.
