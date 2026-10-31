---
type: "Change"
change_type: "added"
title: "A new hook script now enforces two review-loop rules that were prompt text alone"
description: "A new hook script now enforces two review-loop rules that were prompt text alone."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-22T00:00:00-05:00"}
seq: 2
kind: "behavior"
components: ["agent/review-loop", "agent/code-reviewer"]
evidence: ["census", "judgment"]
watches: []
---

## Change

A new hook script now enforces two review-loop rules that were prompt text alone. When a review loop stops, the hook reads the loop's transcript. If a fix coder ran after the last code-reviewer read, the hook blocks the stop once and tells the loop to run the pass over the unread fix diff. A read is a fresh reviewer dispatch or a message to a reviewer the loop dispatched. A second stop in a row passes, so a stuck loop cannot spin. A `no-review` word in the loop prompt exempts the run. Before a review-loop dispatch from the implement skill, the hook denies a prompt with no `handoff:` line. Any parse error fails open and prints why. The settings register it on the agent-dispatch event and on the subagent-stop event, scoped to the review loop.

## Evidence

census, judgment

## Result

Effect unmeasured. Both rules already stood in the prompt text, and the work logs showed the text alone fell short: in 69 of 240 runs with a fix coder, the last dispatch was not a reviewer or a specialist, 55 of 69 repairs driven by a specialist finding got no later reviewer read, and three in four review dispatches from the implement skill once carried no handoff block. The aim is output quality, from no loop that ends on an unread code change. The price is one more reviewer pass in the runs the hook blocks, at the work median for one reviewer dispatch on the largest model. Live checks: the share of runs with a fix coder whose last dispatch is a reviewer, baseline 171 of 240, expected near all; the share of repairs driven by a specialist finding with a later reviewer read, baseline 14 of 69; the count of hook blocks per week; the count of handoff denials, expected near zero once the skill obeys.

## Watch

—

## Back-out

remove both settings entries.
