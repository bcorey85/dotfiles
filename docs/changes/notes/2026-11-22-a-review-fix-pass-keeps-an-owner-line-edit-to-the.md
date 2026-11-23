---
type: "Change"
change_type: "fixed"
title: "A review fix pass keeps an owner-line edit to the scripts CLAUDE.md under a standing ruling"
description: "A review fix pass keeps an owner-line edit to the scripts CLAUDE.md when a standing ruling covers owner lines; in progress, filled out in Phase 4."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T22:21:14-06:00"}
seq: 38
kind: "fix"
components: ["script/owner-lines"]
evidence: ["queue item"]
watches: []
test: "tests/scripts/test_owner_lines.py::OwnerLinesOnlyTest.test_every_other_edit_is_false"
asked: ""
proof: []
unmeasured: "No intake number reads it; the queue item that reported it is the evidence."
---

## Change

Phase 1: `lib/owner_lines.py` reads the owner-line format of the scripts CLAUDE.md and says whether an edit only adds or updates owner bullets. Phase 2: `lib/standing_rulings.py` accepts `covers: owner-lines` beside `covers: rewords`, read by `owner_line_ruling`. Phase 3: the review loop keeps a ruled owner-line edit instead of reverting it. Phase 4 completes this note.

## Evidence

Queue item: review-fix-pass-lets-an-owner-line-edit-in-the.

## Result

New tests fail without the helper.

## Watch

None.

## Back-out

Revert the commit.

