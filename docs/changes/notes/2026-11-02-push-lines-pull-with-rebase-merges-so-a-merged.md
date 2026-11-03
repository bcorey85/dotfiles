---
type: "Change"
change_type: "fixed"
title: "Push lines pull with rebase=merges so a merged branch keeps its merge"
description: "A push line on a branch that holds a merge commit no longer replays the merged commits one by one and stops on conflicts the merge already resolved."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-02T16:40:21-06:00"}
seq: 11
kind: "fix"
components: ["rule/global-claude-md"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_a_push_line_pulls_with_rebase_merges_and_autostash"
asked: ""
proof: []
unmeasured: ""
---

## Change

The global push-line rule now runs `git -C <repo> pull --rebase=merges --autostash` before the push, in place of `pull --rebase --autostash`.

## Evidence

A work session ran the rule's line on a branch whose history held a merge of another branch. Plain `--rebase` linearized the merge, replayed the merged commits and stopped on conflicts the merge had resolved; the session aborted and re-ran with `--rebase=merges`. On a linear branch the two flags do the same thing.

## Result

Push lines keep a branch's merge commits and match plain rebase on linear branches.

## Watch

None: rule fix with no intake number.

## Back-out

Change `--rebase=merges` back to `--rebase` in CLAUDE.md's Safety Rails and drop the test.
