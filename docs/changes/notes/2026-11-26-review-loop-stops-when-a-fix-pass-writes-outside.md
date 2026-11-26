---
type: "Change"
change_type: "fixed"
title: "review loop stops when a fix pass writes outside the reviewed repo"
description: "A review-loop fix pass that writes a file outside the reviewed repo ends the run in a critical-blocker that names each resolved path; the file is left in place."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T04:10:15-06:00"}
seq: 3
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_scope_guard.py::ScopeGuardLoopTest::test_a_fix_pass_write_outside_the_reviewed_repo_stops_with_a_blocker_and_is_left_in_place"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

The loop names each coder call's session (`--session-id`) and reads that transcript for the files the pass wrote with Write, Edit, MultiEdit and NotebookEdit. A path that resolves outside the reviewed repo, and outside the temp and scratch folders, ends the run in a `critical-blocker` that names each resolved path (a symlink reads as its target). Nothing is put back. A pass that died, timed out or returned no final report is read the same way, so its blocker names the paths too. A missing or unreadable transcript leaves a `tool_fault` note and does not stop the run.

`claude/.claude/scripts/CLAUDE.md` names both new owners: `review/review_loop_outside_writes.py` and `review/review_loop_criteria_quotes.py`, with `plan_format.ac_quotes` and `plan_ac_quotes`.

## Evidence

Judgment from the incident: a fix pass wrote to a sibling checkout, and the scope guard, which watches the repo only, never saw it.

## Result

The loop tests pass: the outside write, the died pass, the timed-out pass with no reply, the no-final-report pass and the symlink case each end in `critical-blocker` naming the path; a pass with only inside writes converges with no fault note.

Gap: a write made through Bash (`sed -i`, a redirect, a helper script) is not seen; the transcript names only editor-tool writes (Q5).

## Watch

None: a test pins it.

## Back-out

Remove `review_loop_outside_writes.py` and its call sites in the coder, the partial-fix died-pass blocker, the loop script and the main module, then `git revert` the rest (which also drops the loop-chosen `--session-id` in `review_loop_calls.py`).
