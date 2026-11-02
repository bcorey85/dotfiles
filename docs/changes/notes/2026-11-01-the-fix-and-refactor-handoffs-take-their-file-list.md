---
type: "Change"
change_type: "fixed"
title: "The fix and refactor handoffs take their file list from git"
description: "/fix's scoped rerun and /refactor's handoff now list what git shows changed, so no handoff can leave out a changed file."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T19:39:28-06:00"}
seq: 459
kind: "fix"
components: ["skill/refactor", "skill/fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_the_scoped_rerun_files_come_from_git_not_from_the_packets_files_touched"
asked: ""
proof: []
unmeasured: ""
---

## Change

`script_utils.changed_files` and `lib/handoff_files.py` hold the shared logic, and /code, /fix and /refactor all use them. /fix's scoped rerun and /refactor's handoff list git's changes against HEAD, untracked files included. A listed path keeps its `change` text; any other path gets a stock line. `handoff.files` is now optional in /refactor.

## Evidence

The /code handoff already moved to git after bench handoffs left out changed files. These two paths kept the hand-built list.

## Result

Six new tests fail on the old code and pass on the new. See the branch report for the suite count.

## Watch

None. For /fix, HEAD can include other uncommitted work, so a scoped rerun can be wider than the fixes alone. Reviewers see the whole dirty tree anyway, so it stays.

## Back-out

Revert the branch merge.
