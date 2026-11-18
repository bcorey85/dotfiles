---
type: "Change"
change_type: "fixed"
title: "a code phase start moves the last hand-off aside and a review start with no hand-off stops loudly"
description: "`phase_start.py` moves `handoff.txt` to `handoff.prev.txt`, so a phase review can no longer start on an earlier phase's hand-off text; `code_review_start.py` stops with the path when the file is missing."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-18T00:17:26-06:00"}
seq: 2
kind: "fix"
components: ["script/phase-start", "script/code-review-start", "script/code-wait", "skill/code"]
evidence: ["stale-handoff-guard-misses-when-the-prior-phase"]
watches: []
test: "tests/scripts/test_phase_start.py::PhaseStartTest::test_the_last_handoff_is_moved_to_handoff_prev_replacing_an_older_one"
asked: ""
proof: []
unmeasured: "One clause in skills/code/SKILL.md now says a resume reads `handoff.prev.txt` when a phase start moved `handoff.txt` aside. No rule-meter run: it names the file the script now leaves, and asks for no new behavior."
---

## Change

`phase_start.py` moves `<run folder>/handoff.txt` to `handoff.prev.txt` the way it moves `stop.md` aside, with a
reported, non-fatal failure. Both file names are constants in `code_wait.py`. `code_review_start.py` exits non-zero
with the path and the fix when the hand-off file is missing, with no traceback. The digest guard stays.

## Evidence

A resumed run started the review before it wrote the Phase 6 hand-off. `handoff.txt` still held Phase 5's text, which
had no `handoff-phases.json` entry, so the guard recorded it as Phase 6's.

## Result

Three new tests in `tests/scripts/test_phase_start.py` and one in `tests/scripts/test_code_review_start.py`.

## Watch

None.

## Back-out

Revert the commit.
