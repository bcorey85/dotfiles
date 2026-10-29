---
type: "Change"
change_type: "changed"
title: "The global naming rule was rewritten: take names from the ticket and the code's domain terms"
description: "The global naming rule was rewritten: take names from the ticket and the code's domain terms, never name a value for its container or role alone, and keep every qualifier the domain needs (`compareDateRangeErrors`, not `compareErrors`)."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-27T00:00:00-05:00"}
seq: 11
kind: "behavior"
components: ["rule/global-claude-md"]
evidence: ["removal round", "judgment"]
watches: []
---

## Change

The global naming rule was rewritten: take names from the ticket and the code's domain terms, never name a value for its container or role alone, and keep every qualifier the domain needs (`compareDateRangeErrors`, not `compareErrors`).

## Evidence

removal round, judgment

### Anchor reasons

Anchor `CLAUDE.md`, section `## Engineering Judgment` (evidence: removal round, seeded round, judgment):

About 160 words, three rules. Naming: take names from the domain terms, never name a value for its container alone, keep every needed qualifier, single letters only for loop indexes. With it the coder kept qualifiers on sibling error lists that it dropped without it, and the container clause is untested. Layout: steps split by blank lines, a lookup kept with its guard, early returns, no call result passed straight into a call that is itself an argument. It is judgment from user reports of dense code, and a write-time hook for the same shapes waits on calibration. Design now: no helper or type deferred to a later caller, placement by what the logic knows, and only unrequested features cut. Its placement half held on the coder in a seeded round, and the rest is judgment. Loads in every main session and subagent.

## Result

Run as the coder on finished code whose new identifiers were placeholders, with the domain terms only in the surrounding code. With no rule and with the old rule, the coder named each error list inside three sibling validators plain `errors` or `problems`, and named the test class `ValidationTest`. With the new rule it kept the qualifier on all of them, for example `compare_date_range_errors`. Flagged names: 4 of 30 slots with no rule, 4 of 45 with the old rule, 1 of 45 with the new one. No arm wrote a lazy container name such as `keeperRows` or `input`, so the container clause is untested. One run per task, and the no-rule baseline stayed under the size set to seal a full round, so the user adopted the rule by judgment. About 14 more words than the old rule, measured at 38 more tokens on every main-session and subagent request, about 0.85M tokens a week.

## Watch

—

## Back-out

restore the old rule from git.
