---
type: "Change"
change_type: "fixed"
title: "Review resume records session rulings with --by session"
description: "The review fork's Resume step passes --by session to asks-done, asks-done --correct and decide when the resume text carries a 'ruled by: <session name>' line, and --by user for any other text. The stop footer tells a session that answers to add that line, and the ask presentation names each conditional ask to answer with 'modified:'."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-14T11:36:05-06:00"}
seq: 1
kind: "structured"
components: ["shared/review-fork-run", "script/review-fix"]
evidence: ["rule meter", "judgment"]
watches: []
test: ""
asked: ""
proof: ["2026-11-14-review-resume-rulings-the-ruled-by-footer-and-the"]
unmeasured: "No intake number counts session rulings logged as the user's."
---

## Change

`skills/_shared/review-fork-run.md`: the Resume paragraph passes `--by session` to `asks-done`, `asks-done --correct`
and `decide` when the resume text carries a `ruled by: <session name>` line, and `--by user` for any other text. The
STOP footer's next-to-last line is `A session that answers adds the line ruled by: <its session name>.`, before
`To go on: /<skill> resume <your feedback>`, which stays last.

`review/review_fix.py` `asks_done_line` names the conditional asks ("if yes, deny X") to answer with
`modified:<change with no condition>`, through `review_fix_asks.conditional_ask_numbers`, which
`refuse_conditional_changes` also uses.

## Evidence

judgment: an orchestrating session's ruling, passed in a resume, was logged as the user's sign-off, and its `rejected`
on a conditional change was refused mid-run.

## Result

| Scenario | Rule on | Rule off |
|---|---|---|
| RF01 Resume step, `--by session` | 6 of 6 | 3 of 6 |
| RF03 stop footer names the ruler line (shipped wording) | 9 of 9 | 0 of 9 |
| RF02 stop footer names the ruler line (earlier wording) | 9 of 9 | 0 of 9 |

RF01 had 6 of 18 runs per arm with no gradeable call. The ask presentation line is covered by
`test_the_ask_presentation_names_the_conditional_asks_to_answer_modified_and_no_others` in
`tests/scripts/test_review_fix_script.py`.

## Watch

None.

## Back-out

Revert the commit.
