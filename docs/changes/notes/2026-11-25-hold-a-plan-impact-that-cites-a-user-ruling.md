---
type: "Change"
change_type: "fixed"
title: "Hold a plan impact that cites a user ruling"
description: "A plan impact with no criterion change that quotes or points at a sign-off line the user ruled in the decision log is held for a ruling instead of adopted as code-wins."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T16:23:36-06:00"}
seq: 5
kind: "fix"
components: ["script/review-loop-ruled", "script/signoff-lines"]
evidence: ["tests/scripts/test_review_loop_ruled.py"]
watches: []
test: "tests/scripts/test_review_loop_ruled.py::UserRulingImpactTest::test_an_impact_quoting_a_user_ruled_line_is_held_and_prints_no_deviation"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

route_plan_items records an impact as not adopted and holds it for a ruling when it names the decision log (or the plan's Plan Deviations) and quotes, or points by line number at, a dated sign-off line whose owner is the git user name or `the user` (what a `--by user` ruling writes); any other owner is a session. A coder's PLAN-IMPACT is held the same way. A quote of any line of a user-ruled entry (a line of three or more words, or the whole entry), or a pointer at any of its line numbers, matches; the ruler need not sit on that line. The `The ruling:` text that `ruling_deviation` writes after a blank line belongs to the entry above it, quoted with or without its label. A `the user's ...` owner is a session. signoff_lines.py gains `cites_user_ruling`, `is_user_ruled_line` and `signoff_entry_ranges`.

Forms that make a line user-ruled (the line must hold a date):

- Label: the line opens with `User ruling`.
- Subject: `<git user name or the user> ruled|approved|signed off`, at the line start or after `.`, `:` or `;` and a space.
- Owner after `<ruled|rulings|adopted|decided|cut|reworded|narrowed|signed off> by`: a user name, or `user`.
- Trailing owner: the line ends with `(<user name or user>, <date>)`, as in `## Signed off: <what> (user, 2026-11-21)`.
- Leading owner: `User sign-off, <user name>` or `User sign-off: <user name>`.

Any other owner, such as a session name, is a session.

## Evidence

`UserRulingImpactTest` fails before the change: the impact was adopted and printed a Plan Deviations line that reversed the ruling. Impacts that cite no log, quote no line, or quote a session-ruled line are still adopted by rule.

Sweep over every real decision log (40 plan files with a decision log or a `## Plan Deviations` section, in this repo's `docs/plans` and `~/dev/*/docs/plans`): of 95 dated sign-off lines that mention the user or the git user name, 29 are classified user-ruled, parsed 29 of 95. The 66 others, none a script gap, are:

- Session rulings that say `not the user` (`Ruled by the session, not the user at ...`, `Ruled by agent-evals-c3-owner ... under the user's standing rule`, `not a user sign-off`): bad input for this reader, correctly sessions.
- `code-gates-1123/03-decisions.md:107` (`deleted at the user's request`) and `review-owner-1122/03-decisions.md:37` (`the user's ruling (Q2, ...)` inside a lane's reasoning): they name the user in prose and carry no ruler form, bad input.
- Pending or quoted review text (`review-loop-batch-2/plan.md:90` `no user sign-off yet`, plan-drift quotes): bad input.

The sweep found two script gaps, fixed here: `User sign-off, <name>` lines (`queue-fixes/plan.md:43-45,49-50,52`, `coder-worktree-fixes/plan.md:181`) and a subject form after a sentence break (`review-loop-nov23/03-decisions.md:147`). The `## Signed off: ... (user, 2026-11-21)` headings (`shell-gates-round-two/03-decisions.md:22,30`) were a gap fixed in the same change.

## Result

A reviewer or coder impact that quotes, or points by line number at, a dated sign-off line the user ruled is held, never recorded as overridden by the code.

## Watch

None.

## Back-out

Revert the commit.
