---
type: "Change"
change_type: "fixed"
title: "Review loop hands a ruled sign-off finding back to the caller"
description: "A user- or session-ruled finding on a sign-off line no longer reaches the coder or comes back as a [sign-off] ask; the loop hands it back as a caller step naming file, line and ruled text, outside the round cap."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T02:47:58-06:00"}
seq: 1
kind: "fix"
components: ["script/review-loop-script", "script/review-loop-ruled", "script/review-fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::SignoffLinesLoopTest::test_a_session_ruled_finding_on_a_sign_off_line_is_handed_back_to_the_caller"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`review/review_loop_signoffs.py` `split_signoff_items` holds back a user- or session-ruled finding that hits a sign-off
line. The coder never sees it, and no `[sign-off]` ask is filed for it. The packet, the rendered hand-back and every stop
carry it as a `Caller step:` line with the file, the line and the ruled text. It does not count toward the round cap.
The loop still never edits a sign-off line. The owner line in `claude/.claude/scripts/CLAUDE.md` says so.

The cap-reached stop also names the uncommitted change, so the dirty tree it leaves is no longer a bare "stays dirty":
`review/uncommitted_hunks.py` prints, each behind an `Uncommitted: ` prefix so a caller does not copy one into a
handoff, one `path:first-last` line per changed run, `path (changed)` for a binary, mode-only or renamed file with no
line run, `path (deleted)` and `path (untracked)`. A clean tree gives one "no uncommitted change" line; a failed git
call gives "not read: a git call failed"; a packet whose repo is gone gives "not read" with the reason.

## Evidence

Judgment: a relayed ruling on a Plan Deviations line came back as a fresh `[sign-off]` ask on each resume, and the run
reached the cap. The loop tests drive a fix-first run with `session-ruled:` and `user-ruled:` headers and a control
with no ruling.

## Result

A ruling is applied once by the caller and is not asked again.

## Watch

None: the next resume that carries `ruled by:` on a sign-off line ends with a caller step instead of an ask.

## Back-out

Revert the commit; ruled sign-off findings go back to being filed as asks.
