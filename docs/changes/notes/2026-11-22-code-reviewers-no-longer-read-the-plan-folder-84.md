---
type: "Change"
change_type: "fixed"
title: "Code reviewers no longer read the plan folder: 84-96k chars of tool output each → 33-36k"
description: "A /code phase review leaves the plan's folder out of the reviewers' file list, the handoff's files list and the brief's diff command, and the brief names the plan lines of the phase and says to read only those."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-22T10:33:54-06:00"}
seq: 4
kind: "fix"
components: ["script/review-loop-script", "script/code-review-start", "script/plan-format"]
evidence: ["queue item code-reviewers-spend-most-tokens-reading-plan-docs: in one six-file phase each of two code reviewers took in 130-140k chars of tool output, about 100k of it the uncommitted plan folder (spec, research, decisions), against about 6k chars of code under review"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_the_review_scope_leaves_out_the_plan_folder_unless_the_caller_names_its_files"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/plan_format.py` owns four new helpers: `plan_folder` (the folder of the `plan:` path, when it is a folder of its own under `docs/plans/`), `outside_plan_folder` (a file list or mapping without the paths under it), `plan_folder_exclude` (the `:(exclude)<folder>` pathspec) and `phase_line_range` (the 1-based lines of a phase's section).

- `LoopRun.review_scope` drops the plan folder from the files every reviewer of the run owns (code, smell and test reviewers), unless the caller named files with a `files:` line.
- `code_review_start.handoff_with_git_files` drops it from the handoff's `files:` list.
- `reviewer_brief` writes the diff command as `git diff <base> -- . ':(exclude)<folder>'`, says untracked files under the folder are out, says the folder holds plan documents and not the change, lets a reviewer open only the phase's section, `acceptance-criteria.md` and `00-ticket.md` there, and adds ``Phase N is the `<heading>` section of the plan, lines A-B at the run's start. Read only that section of it.``

The fix coder's Files in scope list leaves out plan-folder files unless a finding names one. The diff backup of a pass and the final read follow the review scope: they leave plan-folder files out unless a `files:` line names one, and a finding naming one does not bring it in. The lint pass covers a plan file only when a coder pass touched it. `changed_files_since` still tracks a coder edit to the plan. A review with no plan, or with a plan that has no folder of its own under `docs/plans/`, keeps the whole diff.

## Evidence

Bench trees under `~/dev/evals/review-plan-scope/`: a four-file change (6.6k chars of diff plus a 1.2k new file) with an untracked 213k-char plan folder, first review round only, one run per arm, tool-output chars counted from each reviewer's transcript.

| reviewer | before | after |
| --- | --- | --- |
| code-reviewer 1 | 96,117 | 35,874 |
| code-reviewer 2 | 84,429 | 32,534 |
| smell-reviewer | 34,793 | 31,143 |

After the change each code reviewer read the phase's plan lines once (6.3k and 6.7k chars) and no other plan file. Before, one read the decisions and criteria files and a 38k saved tool result, the other 16.7k of other spec sections.

A third run, after the brief began to allow `acceptance-criteria.md` and `00-ticket.md` and to name the phase heading: 32,769 and 32,400 chars for the two code reviewers, 28,660 for the smell reviewer. Neither code reviewer opened the criteria or the ticket file.

## Result

Both code reviewers are under the 40k target. Token totals fell from 328k and 417k to 145k and 88k (111k and 141k in the third run). The four changed test files and the full suite pass (5240 tests, 0 failed).

## Watch

A reviewer that misses a defect because the rule it broke sits in a plan section outside the phase's lines, or in the decisions file. A reviewer that reads the plan folder anyway.

## Back-out

Revert the `outside_plan_folder` call in `LoopRun.review_scope` and in `handoff_with_git_files`, and restore `reviewer_brief` to the plain `git diff <base>` line.
