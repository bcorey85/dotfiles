---
type: "Change"
change_type: "changed"
title: "a /review launch carries the plan and its decision log"
description: "review_launch.py takes --plan (default: the code-phase record's plan when that file is in the repo) and writes it into the prompt header; the reviewer brief opens the plan's 03-decisions.md and says a question a recorded ruling answers is not an ask."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T17:29:53-06:00"}
seq: 4
kind: "fix"
components: ["script/review-launch", "script/review-loop-script", "skill/review"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_launch.py::ReviewLaunchTest::test_the_plan_of_the_code_phase_record_reaches_the_prompt_header"
asked: ""
proof: []
unmeasured: "The brief line that a question a recorded ruling answers is not an ask: no rule-meter scenario fits, so its effect on filed asks is unmeasured."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`review_launch.py` takes `--plan <path>`. With no flag it reads the plan from the repo's code-phase record when that file
is in the repo, and writes `plan: <repo-relative path>` into the prompt header. A `--plan` that is no file in the repo
stops the launch; a recorded plan that is no file in the repo is skipped. `reviewer_brief` lets the reviewer open the plan folder's `03-decisions.md` and says a question a
recorded ruling answers is not an ask. The /review skill maps `plan=<path>` to `--plan`.

## Evidence

Judgment: a /review launch on a lane branch named no plan, and its reviewers filed three asks that repeated recorded
rulings. The header and brief tests failed before the change.

## Result

A /review launch in a /code lane carries the plan and its decision log to the reviewers.

## Watch

None.

## Back-out

Revert the commit: /review launches name no plan again.
