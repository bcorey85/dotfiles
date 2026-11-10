---
type: "Change"
change_type: "fixed"
title: "The /code ask-outcome call passes its free text to log-review-finding on stdin"
description: "`log-review-finding desc=-` reads the text from stdin, and the /code ask-outcome call passes its one-line ruling in a quoted heredoc, so quotes, backticks and semicolons in it no longer split or run as shell and the outcome row is logged."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-09T22:13:15-06:00"}
seq: 5
kind: "fix"
components: ["skill/code", "shared/finding-log"]
evidence: ["log-review-finding-fails-on-free-text-argument"]
watches: []
test: "tests/scripts/test_log_review_finding.py::TestAuditRowTest::test_the_code_skill_ask_outcome_call_logs_text_with_quotes_and_backticks_under_zsh"
asked: ""
proof: []
unmeasured: "The /code SKILL.md and finding-log.md edits change call syntax only (desc=- with a quoted heredoc, and the ask-outcome call drops its $(...) repo= and branch=, which the script derives itself); they add no behavior rule. The test pins the call."
---

## Change

- `skills/review/log-review-finding`: `desc=-` reads the desc text from stdin; empty stdin is refused (exit 1, no row).
- `skills/code/SKILL.md` step 5: the ask-outcome call runs by its `~/.claude` path, drops `repo="$(...)"` and `branch="$(...)"` (the script reads the branch and the ledger derives the repo), and passes `desc=- <<'DESC'` with the ruling on the heredoc line.
- `skills/_shared/finding-log.md`: a call that carries text passes `desc=-` and a quoted heredoc.
- The other callers pass desc as one argv item from Python (`review_loop_script.py`, `verify-log`, `refactor_flow.py`), so no shell reads their text; they are unchanged.

## Evidence

Queue item `log-review-finding-fails-on-free-text-argument`: both ask-outcome calls of a /code run failed on argument quoting and the rows were lost.

## Result

The new test fills the SKILL.md ask-outcome block with `don't run "make test" twice; use `make check` instead` and runs it under `zsh -f`. On the old block it fails: zsh ran `make check` as a command substitution and the logger refused the split word `test twice; use  instead`. On the new block it exits 0 and the outcome row lands. A second test pins that `desc=-` with empty stdin is refused. Suite: `bash tests/run.sh` passes.

## Watch

None.

## Back-out

Revert the commit.
