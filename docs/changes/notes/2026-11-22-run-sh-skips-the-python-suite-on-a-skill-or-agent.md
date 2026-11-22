---
type: "Change"
change_type: "fixed"
title: "run.sh skips the Python suite on a skill or agent markdown change"
description: "tests/run.sh runs lint and only the 16 test files that read a skill or agent file when every change is skill or agent markdown, and the full suite otherwise."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T15:35:28-06:00"}
seq: 34
kind: "fix"
components: ["script/tests-run"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_run_sh.py::RunShTest::test_a_markdown_only_change_runs_lint_and_only_the_prompt_reading_tests_and_says_so"
asked: ""
proof: []
unmeasured: "a dev-tool run time; no intake number reads it"
---

## Change

`tests/changed_scope.py` lists the changes as the work tree against the merge base with origin/master (committed, staged, unstaged and untracked files), so a committed branch counts as much as an edit. When every path is a `.md` file under `claude/.claude/skills/` or `claude/.claude/agents/`, `tests/run.sh` still runs lint and the duplicate check, prints "markdown-only change: skipped the unit tests", and runs only the 16 test files in `PROMPT_READING_TESTS` (the tests that open a real skill or agent file). `tests/scripts/test_prompt_reader_list.py` enforces the list: it scans every `test_*.py` for a prompt-reader signal (a skills/agents path helper, a prompt folder walk, or the name of a prompt-loading module) and fails when a matching file is neither in `PROMPT_READING_TESTS` nor in `SIGNAL_BUT_NO_PROMPT_READ` (with a reason), or when a listed file stops matching. Dropping `test_log_escape.py` from the list made it fail; restoring it passed. Any other path, mixed paths, a clean tree, or a git failure runs the full suite.

## Evidence

census: one work-log session changed two skill markdown files and waited on 5232 tests in 179 files (500 s wall, 2572 s summed). Recording every Python open of a real skills/ or agents/ markdown file during a full run found 15 test files that read one (the review-loop script tests read the coder and reviewer prompts); test_rule_anchors reads them in awk and is kept by hand.

## Result

Test for the skip: `tests/scripts/test_run_sh.py::RunShTest::test_a_markdown_only_change_runs_lint_and_only_the_prompt_reading_tests_and_says_so`; the full-suite case is `test_any_other_change_runs_the_full_suite_with_no_skip_message`, and `tests/scripts/test_changed_scope.py` pins the change set (committed, staged, unstaged, untracked, no origin/master).

Measured on a machine shared with two other suite runs, so wall-clock is inflated by the shared slots: a full run 783 s wall and 2119 s summed; the markdown-only run 713 s wall and 601 s summed (1065 tests in 16 files, lint 2 s). The summed seconds are the contention-free figure: 72% less. The review-loop script tests (468 s summed of the 601) stay because they read the prompts.

## Watch

None.

## Back-out

Revert the commit.

