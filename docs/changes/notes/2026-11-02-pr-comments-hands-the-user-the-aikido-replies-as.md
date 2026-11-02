---
type: "Change"
change_type: "fixed"
title: "pr-comments hands the user the Aikido replies as one line"
description: "The Aikido triage replies reach the PR through one `!` line the user runs, in place of a `gh api` call the session's hook always denies."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-02T16:40:22-06:00"}
seq: 13
kind: "fix"
components: ["skill/pr-comments"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_pr_comments_hands_the_user_the_aikido_replies_as_one_line"
asked: ""
proof: []
unmeasured: ""
---

## Change

pr-comments no longer runs `gh api --method POST .../replies` itself. It lists each Aikido reply and hands the user one `!` line that posts them all, with the repo's owner and name written out.

## Evidence

The work machine's safety hook denies every mutating `gh api` call from a session, so the skill's reply step could never run and the user had to post each reply by hand.

## Result

The replies post in one user step. A narrow allow for the replies endpoint is the work repo's gate decision, not this skill's.

## Watch

None: wording fix with no intake number.

## Back-out

Restore the earlier `gh api` block in skills/pr-comments/SKILL.md and drop the test.
