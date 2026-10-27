---
type: "Change"
title: "Push and PR open list unchanged deferred bug findings"
description: "A PreToolUse hook on Bash lists the branch's deferred bug and correctness findings whose code has not changed since review, each time Claude runs git push or gh pr create. It adds context and never denies."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T16:57:07-05:00"}
seq: 16
kind: "behavior"
components: ["script/deferred-push-check"]
evidence: ["census", "judgment"]
watches: ["deferred-severe-unchanged"]
test: ""
unmeasured: ""
---

## Change

New `claude/.claude/scripts/review/deferred_push_check.py`, registered as a PreToolUse Bash hook. On a statement that is `git push` (git global options allowed) or `gh pr create`, it reads `~/.claude/review-findings.jsonl`. It keeps the rows of this repo and branch that review deferred, with class bug or correctness. It lists each one whose lines (line ± 5) no commit changed since the finding. The base is the finding's head commit for committed code. For uncommitted code it is the first commit after the finding that touches the file. Up to 20 rows, as `additionalContext`, with a closing line: fix each with /fix, or name it as carried with its reason. It never denies, and any error prints nothing.

The command parser `strip_heredocs`, `clean` and `statements` moved from `gates/wait_loop_gate.py` into `lib/shell_statements.py`, so both hooks share it. Wait-loop behavior is unchanged.

## Evidence

Work-log census, toolkit repos dropped: 98 deferred bug or correctness findings in about 11 weeks. 81 branches carried a deferred finding and 15 got a recap. On branches with no recap, 48 bug or correctness findings stayed unchanged to the branch tip. The recap already lists the queue, so the gap is the trigger. Claude in work sessions ran 34 `git push` and 22 `gh pr` calls in 1.6 weeks, so the trigger fires. On this machine Claude ran neither outside toolkit repos.

Tests: `tests/scripts/test_deferred_push_check.py`, 14 tests; with `main()` stubbed out, 9 fail. Full suite 2005 tests in 51 files, 0 failed. Ruff is not installed on this machine, so lint did not run; line length was checked by hand.

## Result

Pending the watch.

## Watch

`deferred-severe-unchanged`: the share of deferred bug or correctness findings unchanged at the tip of a branch idle 3+ days, by finding day, from the new day rows of `deferred-followthrough.txt`. Good direction down. A finding counts only once its branch is idle, so a day's reading can still grow for a while after the edit.

## Back-out

Remove the hook entry from `settings.json` and delete `review/deferred_push_check.py` and its test. `lib/shell_statements.py` can stay; wait-loop uses it.
