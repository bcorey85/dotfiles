---
type: "Change"
change_type: "fixed"
title: "pre-commit refuses a toolkit commit that strands an agent-evals meter scenario or skill list entry"
description: "A commit that stages agent, skill, rule or top-level prompt files now runs agent-evals' drift check on the staged text, so a deleted rule fragment or a skill missing from the skill list is caught before the commit lands instead of at the next agent-evals suite run."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-23T23:27:25-06:00"}
seq: 11
kind: "fix"
components: ["script/pre-commit"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_pre_commit_hook.py::PreCommitHookTests::test_a_drift_problem_in_a_staged_rule_file_refuses_the_commit"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

When the staged set touches `claude/.claude/agents/`, `skills/`, `rules/` or a top-level `claude/.claude/*.md`, the
pre-commit hook exports the staged `.md` files under `claude/.claude` to a temp dir (`git checkout-index`, so it reads
the index, not the work tree) and runs `~/agent-evals/bin/toolkit_drift.py --toolkit <that tree>`. The script checks
that every live rule-meter scenario's rule text is still in its source file exactly once and that the skill folders
match agent-evals' skill list. A problem line that HEAD's tree does not also print refuses the commit with that line;
drift already at HEAD passes with a note. When the script is missing, the
hook prints one note and goes on. Scripts and hooks commits skip the check. The hook deletes nothing but its temp dir.

## Evidence

Judgment from one incident: a toolkit commit removed rule text and a skill, and the agent-evals meter scenarios and
skill list went stale until a later suite run failed and a separate fix commit repointed them.

## Result

Three of the four new hook tests failed on the old hook and pass now; the 12 tests of the file pass. The drift check
on the live tree exits 0, so current commits are not blocked. Timing on the live tree, 7 runs: the export plus drift
check takes a median of 66 ms, next to a median of 14 ms for a bare `python3 -c pass` start. It runs only on commits
that stage prose files under `claude/.claude`.

## Watch

None: a test pins it.

## Back-out

`git revert` the commit.
