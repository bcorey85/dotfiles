---
type: "Change"
change_type: "fixed"
title: "verify-prep tells the verifier to keep the default TMPDIR"
description: "verify-prep's printed run rules tell the plan verifier to keep the default TMPDIR for test runs, so repo tests do not run under a temp dir inside the git tree."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T06:39:45-06:00"}
seq: 9
kind: "fix"
components: ["script/verify-prep"]
evidence: ["plan-verifier-tmpdir-under-git-breaks-repo-tests"]
watches: []
test: "tests/scripts/test_verify_prep_queue_ticket.py::RunRulesTmpdirTest::test_the_run_rules_keep_the_default_tmpdir_and_allow_no_tmp_redirect_ban"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/verify-prep` prints a run rule to keep the default TMPDIR for test runs.

## Evidence

The plan verifier set TMPDIR under the git tree, and repo tests that make git repos in a temp dir failed.

## Result

RunRulesTmpdirTest in `test_verify_prep_queue_ticket.py`.

## Watch

None.

## Back-out

Revert the commit.
