---
type: "Change"
change_type: "fixed"
title: "Aikido replies take an explicit PR number"
description: "review_fix.py packet takes `--pr <number>` and posts the Aikido replies to that PR without asking gh for the current branch's PR, so the replies post from a detached HEAD."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-05T16:49:36-06:00"}
seq: 12
kind: "fix"
components: ["script/review-fix", "skill/fix", "skill/pr-comments"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_an_explicit_pr_number_posts_the_aikido_replies_where_gh_cannot_name_the_pr"
asked: ""
proof: []
unmeasured: ""
---

## Change

`packet_arguments` adds `--pr` (digits only, /fix only). `post_aikido_replies` uses it and calls `gh pr view` only without it. /fix step 2 passes `--pr` with the Aikido targets; /pr-comments hands the fetch output's `pr` number to the fix skill.

## Evidence

judgment: a /fix packet step on a detached HEAD could not post Aikido replies because `gh pr view` found no PR. The new test fails on the base commit and passes after.

## Result

`test_review_fix_script.py` 172 pass; lint clean.

## Watch

—

## Back-out

Remove `--pr`, `pr_number_from_gh` and the `pr_number` parameter; drop the skill lines.
