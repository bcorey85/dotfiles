---
type: "Change"
title: "A multi-line ask stays one ruled-asks entry and indents under its number"
description: "A ruled ask whose text spans lines folds onto one ruled-asks line with its outcome, and the ask listings indent a multi-line ask's later lines under its number."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T06:52:26-05:00"}
seq: 236
kind: "fix"
components: ["script/code-step", "script/review-fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_open_phase.py::AskOutcomesReachLaterPasses::test_a_multi_line_ask_is_one_ruled_asks_entry_with_its_outcome"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step_core.py` `ruled_asks_lines`: the ask text and the user's change fold onto one line, so each ruled ask is
  one `ruled-asks:` entry that carries its `(file_line): outcome, Phase N` suffix.
- `code_step_review.py` `numbered_ask_lines` and `review_fix.py` `ask_listing_lines`: a multi-line ask's later lines
  sit indented under its number, not at column 0. The `Proposed change:` line indents its later lines the same way.

## Evidence

- An ask with folded bullets (a mapping ask, or a colon-ended text ask) holds newlines. The review handoff wrote it
  as `    - {ask}`, so its later lines landed at column 0, outside the `ruled-asks:` block, and the outcome suffix
  attached to the last line only. ruled-asks is what stops a later review from raising the ask again.

## Result

- The new test fails before (the ask spans three lines, two of them outside the block) and passes after. Two more
  pin the indented listings: `test_code_step_open_phase.py::AskOutcomesReachLaterPasses::test_the_question_for_the_user_indents_a_multi_line_asks_folded_lines_under_its_number`
  and `test_review_fix_script.py::ReviewFixScriptTest::test_present_asks_indents_a_multi_line_asks_folded_lines_under_its_number`.
  Two more pin the Proposed change line: `test_code_step_open_phase.py::AskOutcomesReachLaterPasses::test_the_proposed_change_indents_its_later_lines_under_the_number`
  and `test_review_fix_script.py::ReviewFixScriptTest::test_present_asks_indents_a_multi_line_proposed_changes_later_lines_under_its_number`.

## Watch

—

## Back-out

Revert the commit.
