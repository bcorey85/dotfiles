---
type: "Change"
change_type: "fixed"
title: "code_review_start stops on a handoff an earlier phase read"
description: "A live /code review start records which phase read each handoff text and stops, naming <run folder>/handoff.txt, when a later phase passes the same text."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-12T16:26:52-06:00"}
seq: 5
kind: "fix"
components: ["script/code-review-start", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_review_start.py::CodeReviewStartTest::test_a_handoff_an_earlier_phase_review_read_stops_the_next_phase_review"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code/code_review_start.py`: `record_handoff_phase` keeps `{sha256: "<plan>#<phase>"}` (the digest of the handoff text) in
`<run folder>/handoff-phases.json`. A live or detached start whose handoff text an earlier phase already read exits 1
and says to write this phase's handoff to `<run folder>/handoff.txt` with Write. A rerun of the same phase passes, and so does the same
text under another plan; a dry run records nothing. A file that is not valid JSON of that shape stops the start with
its path and the recovery (delete it).

## Evidence

judgment: on Phase 4 of a /code run the fork wrote the handoff to another path, and the review loop read Phase 3's
handoff and reviewed the wrong files with no error.

## Result

Four of the five new tests fail on the old tree and pass. The dry-run test guards that a dry run records nothing.
`test_code_review_start.py` passes (25 tests).

## Watch

None: a fixed stop.

## Back-out

Revert the commit.
