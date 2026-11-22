---
type: "Change"
change_type: "removed"
title: "The plan-verifier reports per-criterion verdicts without a free-form gaps section"
description: "The plan-verifier drops the free-form Gaps section of its report and keeps one done, partial or missing verdict per criterion; across 16 metered runs every verdict matched the planted truth in both arms."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T15:03:43-06:00"}
seq: 22
kind: "user-rule"
components: ["agent/plan-verifier"]
evidence: ["rule-meter on/off runs", "judgment"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: "Only one stack and one plan shape ran (a four-criterion TypeScript plan with no acceptance-criteria file and no ticket); no work-log number reads the saving, since the Gaps text was a restatement of verdict rows."
---

## Change

- `agents/plan-verifier.md` drops the `### Gaps` block of the report format (the item, what is missing, where it looked, what would satisfy it) and rewords the "not a code review" line so a noticed bug is no longer a report line.
- A `partial` or `missing` verdict row already carries what is missing and where the verifier looked (`### Every item`), so the verdict table is the only place a gap is reported. `/verify-branch` reads the verdict table and logs one row per verdict; it never read the Gaps block, so the skill is unchanged.

## Evidence

- Scenario PV01 (`bin/rule_meter_scenarios.json` in agent-evals): a planted late-fee branch with four plan criteria whose true verdicts are fixed (two done, one missing, one partial). The on arm is the agent with the Gaps block, the off arm is the same file without it. The toolkit copy of the on arm already carries the reworded last line of "What this is not" in both arms. The detector (`bin/rule_meter_verifier.py`) reads the verdict table and counts a run as complied when all four verdicts equal the planted truth.

## Result

Neutral level, sonnet, 8 runs per arm. Stack in scope: one TypeScript plan with no ticket; no other stack ran.

| Arm | Verdicts equal to the planted truth | Report has a Gaps heading | Output tokens, mean (median) | Cost per run |
| --- | --- | --- | --- | --- |
| Gaps block kept | 8 of 8 | 8 of 8 | 1351 (1344) | $0.052 |
| Gaps block dropped | 8 of 8 | 0 of 8 | 1322 (1327) | $0.052 |

The per-criterion verdicts are unchanged: 16 of 16 runs gave done, done, missing, partial. Output shrinks 2% (1351 to 1322 tokens), inside the run-to-run spread of 1160 to 1505, so the cut gains little on a plan this small; it removes a section that repeated the missing and partial rows and shortens what the main session reads when a plan has many gaps.

## Watch

None: no work-log number reads this.

## Back-out

Restore the `### Gaps  (omit when clean)` block and the "one line under Gaps" wording from git history of `agents/plan-verifier.md`.
