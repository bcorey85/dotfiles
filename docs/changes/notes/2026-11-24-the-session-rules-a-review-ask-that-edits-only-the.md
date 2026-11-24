---
type: "Change"
change_type: "fixed"
title: "The session rules a review ask that edits only the scripts CLAUDE.md"
description: "A review ask whose only approval-file edit is in the scripts CLAUDE.md is ruled by the orchestrating session, so a lane no longer waits on the user for it"
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T12:07:10-06:00"}
seq: 1
kind: "fix"
components: ["script/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_ask_ruler.py::test_a_session_accepting_the_scripts_claude_md_ask_restores_the_file_and_logs_it"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

The review loop no longer marks an ask user-only when its only approval-file edit is in
`claude/.claude/scripts/CLAUDE.md`, for any edit to that file. `asks-done --by session` records such an ask accepted
or rejected. An ask on any other approval file (another CLAUDE.md, CLAUDE.local.md, AGENTS.md) stays user-only and the session is
still refused. The path test lives in `review_loop_ruled.py` `session_rules_approval_path`; `review_loop_ruled.py`
`mark_user_only` is the one place an approval ask is marked user-only.

## Evidence

Two lanes in one day held a scripts CLAUDE.md ask for the user, and the session could not record its ruling. The user
set that the orchestrating session rules every ask about that file, the whole file and not only owner lines: agent-evals
commit 42090a64.

Review rulings by agent-evals-73 (session) on 2026-11-24: the two scripts CLAUDE.md ask texts drop the line that
the user must approve, and saved entries under the old wording are left orphaned; `session_rules_approval_path` moves
beside `approval_only_paths`; the matching line in the global CLAUDE.md is queued separately.

## Result

Tests in `test_review_fix_ask_ruler.py` and `test_review_loop_ruled.py` fail before the change and pass after.

## Watch

None: no intake number reads it.

## Back-out

Revert the branch commit.
