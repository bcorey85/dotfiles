---
type: "Change"
title: "A text review ask ending in a colon keeps its bullets as one ask"
description: "A plain-text ask whose text ends in a colon takes the plain-text bullets after it, so one finding with sub-points is one ask with one outcome word in place of one ask per bullet."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T06:31:20-05:00"}
seq: 231
kind: "fix"
components: ["script/handback", "script/code-step"]
evidence: ["transcript read"]
watches: []
test: "tests/scripts/test_handback.py::ParseTest::test_bullets_after_a_text_ask_ending_in_a_colon_stay_inside_that_ask"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `handback.py`: `fold_bullets_into_asks` folds the bullets after a plain-text ask whose text (before any
  `|` field) ends in a colon, plain-text or mapping, into that ask, each plain-text bullet kept as a `- ` line.
  Before, only a mapping ask took bullets. A bullet with its own `| path:line` field still starts a new ask, and a
  text ask with no colon takes none. A folded bullet that flags a blocker (`[blocker]` text, or `blocker: yes` in a
  mapping bullet) marks the ask a blocker. A `[blocker]` text bullet after a mapping lead with no `blocker` field
  marks it a blocker; a lead's explicit `blocker` wins.

## Evidence

- A /code review wrote question.md with 4 numbered asks that were one finding: a colon-ended lead line and its
  bullet sub-points each became an ask, and asks-done demanded 4 outcome words for one decision.
- The test that fails on the base scripts and passes now:
  `test_handback.py::ParseTest::test_bullets_after_a_text_ask_ending_in_a_colon_stay_inside_that_ask`.
  `test_a_text_ask_not_ending_in_a_colon_takes_no_bullets` pins that separate text asks stay separate.
  `test_a_blocker_text_bullet_after_a_mapping_bullet_marks_the_text_ask_a_blocker`,
  `test_a_mapping_bullet_with_blocker_yes_marks_the_text_ask_a_blocker` and
  `test_a_blocker_text_bullet_marks_a_mapping_lead_with_no_blocker_field_a_blocker` failed before the blocker part.

## Result

- One finding with sub-points is one ask, answered with one outcome word.

## Watch

- None: no intake counts asks per finding.

## Back-out

- Revert the commit.
