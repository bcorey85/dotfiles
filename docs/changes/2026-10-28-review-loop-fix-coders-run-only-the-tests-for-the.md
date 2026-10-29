---
type: "Change"
title: "Review-loop fix coders run only the tests for the files they changed"
description: "Every coder prompt the review loop builds tells the coder to run only the tests for its changed files, never lint suites, the full suite or repo-wide checks, since the loop runs the full check after the pass."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T13:43:40-05:00"}
seq: 191
kind: "fix"
components: ["agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_every_coder_prompt_tells_the_coder_to_run_only_the_tests_for_its_changed_files"
asked: ""
proof: []
unmeasured: ""
---

## Change

`coder_prompt` adds one rule to every review-loop coder prompt: run only the tests for the files you changed; do not
run lint suites, the full test suite or other repo-wide checks, because the loop runs the full check after the pass.

## Evidence

On one branch fix-coder calls averaged about 1M tokens and peaked at 6.5M, and three ran 590-712 seconds. One fix
coder's report listed the rules check, model lint, Python lint, duplicate lint, a meta-surface run, a domain
consistency run on a reseeded fixture and a lineage verify that timed out.

## Result

The new prompt test fails before and passes after.

## Watch

None yet: fix-coder tokens per call on the next comparable branch is the reading; no intake number splits
review-loop fix coders from other coder dispatches.

## Back-out

Revert the commit; the prompt drops the rule.
