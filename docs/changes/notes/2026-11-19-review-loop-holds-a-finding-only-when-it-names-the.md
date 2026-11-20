---
type: "Change"
change_type: "fixed"
title: "review loop holds a finding only when it names the holding session"
description: "A dirty file is held only while another live session works in the repo, each held file carries a holder row (session and claim), a held correct finding is returned as held_unfixed with that proof, and a file the plan gives to an earlier phase is never held."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T17:09:12-06:00"}
seq: 6
kind: "fix"
components: ["script/code-step", "script/review-loop-script", "script/review-fix", "skill/code"]
evidence: ["review-loop-finding-skipped-as-file-held-by"]
watches: []
test: "tests/scripts/test_code_review_start.py::CodeReviewStartTest::test_a_dirty_file_is_held_only_when_another_live_session_works_in_the_repo"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code_review_start.phase_held_files` builds holder rows from `lib/session_registry.py` live sessions and leaves out
the run's own session and earlier-phase files. The prompt carries a `held by` line. `review_loop_held.py` keeps a
finding on a held file out of the coder only when it has a holder row, and `handback.py` reports it as
`held_unfixed`. Under `--file` scoping, other dirty files get holder rows from the live-session lookup.

## Evidence

Findings on the run's own files were skipped as held by another session that did not exist.

## Result

Held-file tests in `test_code_review_start.py`, `test_review_loop_script.py` (`ImplicitHoldersTest`) and
`test_session_registry.py`.

## Watch

None.

## Back-out

Revert the commit.
