---
type: "Change"
change_type: "fixed"
title: "Phase start and the review loop name a holder by its writes, not its folder"
description: "A /code phase start, its review start and the review loop name a session as holder of dirty files only when that session's transcripts record a write to them, through one shared lookup in lib/dirty_writers.py that pull_keep_index also uses."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T00:34:29-06:00"}
seq: 1
kind: "fix"
components: ["script/phase-start", "script/code-review-start", "script/review-loop-held", "script/dirty-writers", "script/pull-keep-index", "script/session-registry"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_phase_start.py::PhaseStartTest::test_a_live_other_session_in_the_repo_that_wrote_no_dirty_file_is_no_holder"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`phase_start.current_holder`, `code_review_start`'s fallback and `review_loop_held.implicit_holders` named the first
live session whose working folder sat in the repo (`session_registry.other_live_session_in`), so a run could hold
files for, and message, a session that never wrote them. The writer-evidence lookup that pull_keep_index gained moves
into `lib/dirty_writers.py`, and all four callers use it; `other_live_session_in` is deleted. A holder is the one
other live session with a logged write to a dirty path after the HEAD commit (after the recorded head, for a
start record), with every transcript read. Own-session writes are left out when proving the holder. A recorded holder
still holds every start-dirty file. With no recorded holder, the review fallback and the review loop hold only the
paths the proven writer wrote; pull_keep_index keeps its veto on an own write. The start record shape is unchanged. The `scripts/CLAUDE.md` owner line for
`lib/dirty_writers.py` is deferred to a follow-up; `_shared/handoff-block.md` and its rule-anchors row describe the new held set.

## Evidence

A /code run named a peer as holder because it worked in the same checkout, the same folder guess pull_keep_index
had on 2026-11-25.

## Result

New `tests/scripts/test_dirty_writers.py` and holder tests in test_phase_start, test_code_review_start and
test_review_loop_script: a live session that wrote no dirty file is not named. Full suite 6717 tests, 0 failed.

## Watch

A peer's write before the phase commit no longer holds at the next phase (HEAD-time cutoff). A writer whose cwd is
outside the repo is not searched.

## Back-out

Revert the commit.
