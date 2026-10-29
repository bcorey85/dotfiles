---
type: "Change"
change_type: "changed"
title: "`/code` gives the coder a reading list and moves the checks to a hook at hand-back"
description: "`/code` gives the coder a reading list and moves the checks to a hook at hand-back."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-19T00:00:00-05:00"}
seq: 1
kind: "behavior"
components: ["skill/code", "script/coder-gate", "agent/review-loop", "script/coder-packet", "skill/coder-core"]
evidence: ["sealed bench round", "judgment"]
watches: ["coder-packet-handback-gate", "coder-packet-handback-gate-escapes"]
---

## Change

`/code` gives the coder a reading list and moves the checks to a hook at hand-back. For a plan phase, it runs `coder-gate.py set` with the typecheck of each package the phase touches, and lint and tests for only the files the phase changes. `set` refuses a command that runs a whole test suite, lints a whole package or runs a build, because the review loop runs the full check once at its end, and `/code` runs the other Automated Verification commands once after the loop. It then puts the output of `coder-packet.py <plan> <N>` in the coder prompt verbatim. The packet lists the phase, the shared sections it cites, the testing strategy, the acceptance criteria, the files the phase names, one existing sibling per new file and the test helpers. It tells the coder to read them all in its first response, to edit in batches and not to run checks. A PreToolUse hook on `SubagentHandback` runs the gate for coders only, and only while a gate set by `/code` is under 6 hours old. On a failure it refuses the hand-back with the failure tail, up to 3 times, then allows it as `cap`. On a pass or at the cap, it appends the gate result to the hand-back message, with a line that the report is final. After the coder, `/code` runs `coder-gate.py clear` and puts its lines in the handoff's `tests-run`, and a `cap` line also in `flagged`. `coder-core`: a packet replaces the phase-scoped plan read, and the coder runs no checks when the hook runs them. Each gate run is logged to `~/.claude/coder-gate.jsonl`

## Evidence

sealed bench round, judgment

### Anchor reasons

Anchor `skills/coder-core/SKILL.md`, section `## Read the plan phase-scoped` (evidence: removal round, sealed round):

Read the shared sections, your phase, and the testing strategy; a sibling's internals are a PLAN-IMPACT. Kept as the rule only. The rg command and the three-Reads mechanics are gone: without them the coder opened the plan half as often at the same test passes, which is where most of the token saving came from. A packet in the brief now replaces this read. In a sealed round of three runs per arm on one plan phase, a coder that read a script-built list of files in its first response used 0.36 of the standard coder's cache read and 7 responses against 25. The final gate passed in every run, and no plan check or reviewer finding was lost.

## Result

One plan phase, Sonnet coder, three runs per arm. Coder cache read 507,679 against 1,401,626 at the median (0.36). Responses 7 against 25. Final gate 3 of 3 in both arms, 13 of 13 plan checks in both, reviewer bug or major 0 in both. Costs: arm wall +19% (676 s against 568 s), because each hook run is a full typecheck, lint and test pass of 2 to 3 minutes. Coder output 2.6 times higher and cache write 25% higher, both small next to the cache read cut. The round used a bench packet. The general script did not run in it. In a live `/code` run after the round, the general scripts set 4 gate commands and built the packet, and the gate refused once and then passed. The coder's last report still said that a gate re-run was pending, so the main session waited and never cleared the gate or sent the review. The appended gate line is by judgment from that run, and a live probe showed that it reaches the caller. The round's gate ran the whole suite at each hand-back, and that caused the wall rise. The scoped gate and the refusal in `set` are by judgment. A live run with the whole suite took 120 to 131 s per gate run. A live run with path-scoped tests, plus a build and a whole-package lint, took 79 s. The shipped gate drops the build and the whole-package lint too, and its run time is not measured. A scratch test of `set` accepted 10 scoped commands and refused 19 whole-package commands.

## Watch

Sonnet coder cache read per dispatch and responses per dispatch from the weekly token table, and review escapes per review run.

Reading, 2026-10-26 intake: cache read BETTER, kept. Sonnet coder cache read per dispatch fell from 5.38 M before to 1.82 M after, across 284 dispatches. Median responses per dispatch fell from 30 to 14. Test runs per dispatch held at 0.86 before and 0.89 after, so the cut does not come from less checking. The coder whole-package check hook shipped the same day and reads the same metric, so the two cannot be separated. The escape watch stays open: it has only 2 days of escapes so far, 1 in 26 review runs.

## Back-out

delete the `SubagentHandback` entry in `settings.json`, the gate and packet paragraph in `/code` step 3, the clear sentence in step 4, and the packet and hook sentences in `coder-core`
