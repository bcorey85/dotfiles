---
type: "Change"
change_type: "fixed"
title: "test-reviewer never mutates the shared tree"
description: "test-reviewer is told it is read-only and reports a mutation check as a finding instead of running it on the tree its sibling reviewers test."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:46:49-05:00"}
seq: 101
kind: "fix"
components: ["agent/test-reviewer"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_the_test_reviewer_never_mutates_the_shared_tree"
asked: ""
proof: []
unmeasured: ""
---

## Change

- test-reviewer: one paragraph after its role line. It never changes a file in the tree, not even to mutate and
  restore it, because sibling reviewers run tests on the same tree. A mutation it wants is reported as a finding with
  the mutation and the test that should kill it.

## Evidence

- On the work machine review-loop ran code-reviewer, test-reviewer and smell-reviewer in parallel. The test-reviewer
  mutated source files and restored them; the code-reviewer's scoped test run failed in that window, passed on rerun,
  and it spent time diagnosing the other agent's edits. Rounds took 20-25 minutes.
- The test pins the rule; it fails on the base tree. No hook enforces it: test-reviewer has no Write or Edit, so the
  mutation went through Bash.

## Result

- See the branch's suite run.

## Watch

—

## Back-out

Revert the commit.
