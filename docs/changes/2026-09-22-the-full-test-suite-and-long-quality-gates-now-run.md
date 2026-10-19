---
type: "Change"
title: "The full test suite and long quality gates now run once per phase, at the review loop's execution gate"
description: "The full test suite and long quality gates now run once per phase, at the review loop's execution gate."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-22T00:00:00-05:00"}
seq: 4
components: ["agent/review-loop", "agent/test-writer", "agent/code-reviewer", "rule/global-claude-md", "skill/test-audit"]
evidence: ["judgment"]
watches: []
---

## Change

The full test suite and long quality gates now run once per phase, at the review loop's execution gate. Coders, the test writer, the code reviewer and the specialists run only checks scoped to the files they changed or read. The global rule in CLAUDE.md says the same for every session. The loop's gate always runs when the loop ends, and a handoff tests-run no longer exempts it, because that run is now scoped. The implement skill takes the loop's gate as the phase's full-suite evidence. The dependency skill and the test-audit skill no longer add a second full run. The handoff example shows a scoped command. The stop hook script moves to match: it blocks a loop that ends with no full-suite call after the last code change, a loop that returns plan-impact is exempt, and the handoff tests-run exemption is gone.

## Evidence

judgment

### Anchor reasons

Anchor `skills/_shared/reviewer-calibration.md`, section `## Verify the Premise Before Flagging` (evidence: judgment):

Check the code, the rule, and the diff before a finding ships. Adopted by the four specialist reviewers, untested there. The diff reviewer no longer loads it, for the same reason as the block above. By judgment, the typecheck is now scoped to the files in question, and specialists never run the full suite or a long gate. Effect unmeasured.

Anchor `agents/review-loop.md`, section `## Step 6: Convergence — the execution gate` (evidence: removal round, judgment):

The execution gate, the acceptance-spec exception, no test-intent audit here, and the class-closure check before convergence. The trimmed arm dropped the rationale and one example. Typecheck was clean in 24 of 24, no run dispatched test-intent, and no run converged empty past round one in either arm. By judgment, the execution gate is now the phase's one full run and always runs; a handoff tests-run no longer exempts it, because coders now run only scoped checks. Effect unmeasured. By judgment, the line that kept the test-intent audit out of the loop is gone. The loop names no such dispatch, and the code reviewer leaves the cull to the test audit at branch exit. A passed gate now goes to the logs, because no specialist pass follows it.

## Result

Effect unmeasured. The user reported constant waits on full suites. Before the change, each coder, test writer and reviewer was told to run the project's checks, so one phase could run the full suite several times. The aim is wall-clock, with quality held by the one full run before the phase exits. The trade: a break outside the changed files now surfaces at loop end, not during the fix, so the fix has a larger diff to search. A phase that routes a failing test through the fix skill still pays two full runs. The prompt texts add 165 words, paid mostly at each coder, test-writer and reviewer dispatch. Live check: the census section on checker wait time, by who ran the check and full against scoped, before and after.

## Watch

—

## Back-out

restore the prior texts and the prior hook script.
