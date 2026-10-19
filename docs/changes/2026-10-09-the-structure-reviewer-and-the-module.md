---
type: "Change"
title: "The structure reviewer and the module simplification reviewer now run only on Opus"
description: "The structure reviewer and the module simplification reviewer now run only on Opus."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-09T00:00:00-05:00"}
seq: 6
components: ["agent/smell-reviewer", "skill/refactor", "agent/review-loop", "shared/finding-log"]
evidence: ["gate ranking", "seeded round"]
watches: []
---

## Change

The structure reviewer and the module simplification reviewer now run only on Opus. Their Sonnet tiers and separate Opus copies merged into one file each, with the copies' depth paragraphs folded in. `/refactor` loses its `+deep` swap. The `+deep` modifier now omits `model` on every dispatch. The review loop dispatches the structure reviewer by its base name, so its finding log rows change gate name

## Evidence

gate ranking, seeded round

### Anchor reasons

Anchor `agents/smell-reviewer.md`, section `(preamble)` (evidence: removal round, judgment, census, seeded round, gate ranking):

Frontmatter: name, description, model, tools, color. The opus pin: the Opus tier is the highest-yield gate measured, 4.53 findings per run over 15 runs, 91% of them actioned, and the cheapest per actioned finding in the system. In a seeded round Opus tied Sonnet on seeded catches and filed a depth-type defect in 5 of 5 runs against 2 of 5. The review loop sends it beside the first review on every large diff: with it the review caught 45 of 45 planted structure defects over five diffs, without it 39 of 45. The Sonnet tier and its separate Opus copy were merged into this one file on the user's call, so `/refactor` now runs it on Opus too. Identical in both arms apart from the model pin the round set to measure at the loop's tier. Gone later: the project memory line, which had no effect while auto memory is off in the settings. The description is a routing line: what the agent is, who dispatches it, and any rule that the dispatcher needs. A census of this machine's top-level dispatches, a guide only, found none that menu text alone picked, and no dropped dispatcher rule had the description as its only home. The description names both dispatchers: /refactor, and the review loop on a large diff.

## Result

The Opus structure reviewer is the highest-yield gate: 4.53 findings per run over 15 runs, 91% actioned, cheapest per actioned finding. It tied Sonnet on seeded catches and filed a depth-type defect in 5 of 5 runs against 2 of 5. The simplification reviewer on Opus, with its depth paragraph, caught all five seeded shapes in 3 of 3 runs. Sonnet caught the branch-table shape in 1 of 3 and the repeated guard in 0 of 3. Opus filed no decoy. On the clean twin it filed a median of 1 finding against 0. Its median reviewer tokens were cache read 82k against 300k, output 6.0k against 8.8k, and 9 tool calls against 14, but the Sonnet rows include the wrapper session. With the depth paragraph on current Sonnet, the reviewer caught each of the two hard shapes in 2 of 3 runs, against 3 of 3 on Opus. Its median reviewer-only tokens were cache write 21k against 42k, cache read 51k against 114k, and output 3.2k against 7.6k. Cost: every default `/refactor` finder run moves from Sonnet to Opus tokens.

## Watch

Opus tokens for both agents in the weekly census, and simplify findings per run.

## Back-out

restore the four files and the `+deep` swap from git
