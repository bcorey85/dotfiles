---
type: "Change"
change_type: "changed"
title: "finding-log and skimmable-writing fold into their one loader, every escape-ratchet pointer names its trigger, and the test-reviewer cull rule has one owner"
description: "test-audit carries the per-finding log instructions and adr-template carries the skimmable-writing rules; the two shared files are deleted. Each escape-ratchet pointer says when to read it, and the consumer lists of escape-ratchet and code-vocabulary match what rg finds. The test-reviewer cull step points at the test-intent-reviewer cull paragraph."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T18:00:00-06:00"}
seq: 465
kind: "fix"
components: ["skill/test-audit", "skill/adr", "skill/verify-branch", "skill/pr-comments", "skill/commit", "skill/fix", "skill/escape", "skill/cc", "skill/eng-spec", "agent/spec-criteria", "agent/test-reviewer"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_the_test_reviewer_s_cull_step_points_at_the_test_intent_reviewer_s_cull_paragraph"
asked: ""
proof: []
unmeasured: "The two folds, the trigger-naming pointers, the consumer-list corrections and the test-reviewer cull cut. The only cull detector grades the input-shape rule, which lives in the test-intent-reviewer and not in the cut text."
---

## Change

test-audit Logging holds the run and finding row commands and the field rules. The fold dropped the `source=` field, the `fix_induced` rules, the `diff_loc` measuring rule, the silent-run rule, the `line=0` case of the join-key rule, the `gate=` literal-name rule, the no-verdict `result=` omission and `[phase=<index>]`. The shared finding-log file is deleted. adr-template holds the skimmable-writing rules, merged with its two ADR bullets, and the shared skimmable-writing file is deleted. The pointers in verify-branch, pr-comments, commit, fix, escape, cc and the eng-spec plan-review step each say when to read the escape-ratchet file (before picking the guard or before logging the escape). The consumer lines of escape-ratchet and code-vocabulary list the skills, scripts and gates that cite them. Both spec-criteria files say to read code-vocabulary before writing a criterion that names code. The test-reviewer cull step, in the claude agent and the opencode port, applies the test-intent-reviewer cull paragraph.

## Evidence

Each folded file had one loader. The pointers named the file with no trigger, and the consumer lists named skills that never load the files.

## Result

No reference to a deleted file remains, and each pointer names its trigger. The cull rule has one owner.

## Watch

None.

## Back-out

Revert the commit.
