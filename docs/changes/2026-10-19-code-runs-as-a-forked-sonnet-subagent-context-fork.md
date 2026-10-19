---
type: "Change"
title: "`/code` runs as a forked Sonnet subagent (`context: fork`, `model: sonnet`)"
description: "`/code` runs as a forked Sonnet subagent (`context: fork`, `model: sonnet`)."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-19T00:00:00-05:00"}
seq: 6
components: ["skill/code", "script/code-step"]
evidence: ["bench run", "judgment"]
watches: ["code-forked-sonnet-router"]
---

## Change

`/code` runs as a forked Sonnet subagent (`context: fork`, `model: sonnet`). It runs `code-step.py`, a routing script, and does what each ACTION line of its output says. The script builds every coder and review prompt, the handoff, the clean mark, the phase blocks and the text for the user. The Opus main session only starts `/code`, relays the hand-back, and asks the user any question that the hand-back carries, then invokes `/code` again with the RESUME args. A second SubagentHandback hook, `code-step.py hook`, saves the last message of each subagent, so the script reads the coder report and the review packet from a file

## Evidence

bench run, judgment

### Anchor reasons

Anchor `skills/code/SKILL.md`, section `(preamble)` (evidence: bench run, judgment):

Invocation contract: name, description, the tool list, and the fork into a Sonnet subagent with no conversation history. In bench runs the Opus main session made 1 reply per run against 12, and its cache read fell from 614k to 0. The routing replies moved to Sonnet: 12 replies and 357k cache read. Reviewer tokens and the final gate held at parity.

Anchor `skills/code/SKILL.md`, section `# Code` (evidence: bench run, judgment):

The subagent runs the routing script and does what each ACTION line says. The script builds every coder and review prompt, the handoff, the clean mark, the phase blocks, and the text for the user, so the subagent writes none of them. The script carries the routing rules of the earlier text, and its tests pin them. A question goes back to the main session as a QUESTION section with RESUME args, because the forked subagent cannot ask the user. That round trip worked in 3 of 3 bench trials. One bench plan run converged at the second review round, with all tests and 4 verification commands green. The plan-impact branch did not run live. The effect at work is unmeasured.

## Result

In bench runs the Opus main session made 1 reply per `/code` run against 12. Its cache read fell from 614k to 0, with 30k cache write and 1,223 output. Sonnet took the routing: 12 replies and 357k cache read. Reviewer tokens were 2.86M, inside the 2.53M to 3.52M range of the earlier skill. The plan run converged at the second review round, with 311 tests and 4 verification commands green. A question round trip through the main session worked in 3 of 3 trials, at 5 Opus main replies and about 155k cache read per round. The plan-impact branch did not run live.

## Watch

the `/code` share of Opus main-session tokens, and review escapes.

## Back-out

restore the earlier `skills/code/SKILL.md` from git and delete the `code-step.py hook` entry from settings.json
