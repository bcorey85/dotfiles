---
type: "Change"
change_type: "added"
title: "One branch-base script picks the base branch for review-scope, test-reviewer and refactor"
description: "scripts/branch-base prints the default base ref of a branch and where it came from. review-scope, the test-reviewer branch scope and refactor-flow all call it, so the three no longer choose a base each their own way."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-20T23:22:51-05:00"}
seq: 16
kind: "behavior"
components: ["script/branch-base", "skill/review", "agent/test-reviewer", "skill/refactor"]
evidence: ["tests", "judgment"]
watches: []
---

## Change

- New script `scripts/branch-base [--head <branch>]`. It prints the base ref and its source. The first candidate that exists wins: the branch's upstream, `origin/HEAD`, `origin/main`, `origin/master`, local `main`, local `master`. A head named `main` or `master` never uses that list. It takes its same-named upstream, else `origin/<head>`, else an upstream with another name, else prints `STOP:`.
- A candidate that is the head itself, or its remote copy, is skipped. Refs compare as full names, so a local branch called `origin/main` never stands in for the remote one.
- `skills/review/review-scope` takes `MERGE_BASE` from `branch-base`. When the script fails, it prints the reason and leaves `MERGE_BASE` empty. `review-scope-check` covers this.
- `agents/test-reviewer.md` "branch" scope reads the first word `branch-base` prints. On its `STOP:` line the agent asks the user for the base.
- `refactor-flow.py` calls `branch-base` and takes `--base REF` to override.

## Evidence

Tests: 36 branch-base tests, plus the `review-scope-check` families, pass against the installed paths. The test file covers a stale `origin/HEAD`, a head named `main` or `master`, a head that `origin/HEAD` points at, a branch named `origin/main`, and a repository with no commits.

Judgment: three places chose a base by their own order, and a stale `origin/HEAD` or local `master` gave a much wider diff in any of them.

## Result

Installed 2026-10-20. The metrics-switch lines are merged into `review-scope` and `review-scope-check`.

## Watch

None. A wrong base shows as an odd diff size in one review. No edit watch measures it.

## Back-out

Restore the previous `review-scope`, `review-scope-check`, `test-reviewer.md` and `refactor-flow.py` from the dotfiles history and delete `scripts/branch-base`.
