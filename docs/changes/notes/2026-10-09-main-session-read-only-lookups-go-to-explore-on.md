---
type: "Change"
change_type: "changed"
title: "Main session: read-only lookups go to `Explore` on `haiku`, not to `general-purpose` on Sonnet"
description: "Main session: read-only lookups go to `Explore` on `haiku`, not to `general-purpose` on Sonnet."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-09T00:00:00-05:00"}
seq: 2
kind: "behavior"
components: ["agent/general-purpose"]
evidence: ["census", "judgment"]
watches: []
---

## Change

Main session: read-only lookups go to `Explore` on `haiku`, not to `general-purpose` on Sonnet

## Evidence

census, judgment

## Result

Work logs, dotfiles and agent-evals sessions excluded: general-purpose Sonnet ran 134, 128 and 91 dispatches in weeks 39–41, with 442M, 308M and 173M cache read tokens. In weeks 40–41 that was more than the review loop. The read-only share is not yet measured; a work-machine count of runs by kind (read-only, editing, nested) is pending. The main session checks every location a lookup returns, so a wrong answer shows at once. Effect on work: watch weekly general-purpose Sonnet tokens fall and Explore Haiku tokens appear in the agent token table.

## Watch

—

## Back-out

delete the bullet from `orchestration.md`
