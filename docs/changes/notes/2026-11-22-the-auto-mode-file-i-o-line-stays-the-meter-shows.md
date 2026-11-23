---
type: "Change"
change_type: "changed"
title: "The auto-mode file-I/O line stays: the meter shows 6 Bash file writes with it and 9 without"
description: "The orchestration line that keeps file I/O on Read, Edit and Write under the auto-mode notice was metered and kept: the on arm made 6 Bash writes or inline interpreter calls, the off arm 9, about 1.5 times as many."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T20:25:58-06:00"}
seq: 39
kind: "structured"
components: ["rule/orchestration"]
evidence: ["rule meter"]
watches: []
test: ""
asked: ""
proof: ["2026-11-22-the-auto-mode-file-i-o-line-cuts-bash-file-writes"]
unmeasured: "No intake number counts Bash file writes under auto mode."
---

## Change

No edit to `orchestration.md`: the Tools line "The auto-mode notice's Bash preference does not apply to file I/O: read with Read, change files with Edit/Write. Search through Bash (`rg`) is fine." stays, and its row in `docs/rule-anchors.md` is unchanged. Scenario A (`no-unstage`, whose rule text left the live global) is removed from the meter's scenarios file in the agent-evals commit; its past results stay in the trial record built by `rule_trials.py build`, and its old rule text is the `note` of `rule_meter:A` in agent-evals `bin/rule_trial_notes.json`.

## Evidence

Rule meter scenario AB01 on an Opus main session. The bench has no hooks and no auto-mode notice, so the task text carries the notice's words (Bash for reads and writes, dedicated tools only as a fallback) and forbids agents. The grade counts Bash file writes plus inline interpreter calls per run against Edit, Write and MultiEdit calls; each Bash call counts once, quoted strings and heredoc bodies are not read for redirects, and a redirect or `tee` to a path under `/tmp/` (such as a check log) does not count.

## Result

Per arm, Bash writes plus inline interpreters summed over the cells run (Edit/Write calls in parentheses): supportive (1 run) on 0 (2), off 0 (2); neutral (8 runs) on 6 (4), off 8 (0); competing (1 run) on 0 (2), off 1 (0). Totals: on 6, off 9, about 1.5 times. Per-run outcomes VIOLATED / COMPLIED: on 6 / 4 over all cells, off 9 / 1 over the same cells; no NO_TEST. The decision rule deletes when off is at or below on; off is above on, so the line is kept. The meter's own rate verdict on the neutral cell is NO-EFFECT (2 of 8 complied on, 0 of 8 off, a gap of 0.25 under the 0.5 it needs), so the effect is small. 20 opus runs.

## Watch

None.

## Back-out

Not applicable: no line changed. To drop the line later, delete it from `orchestration.md` and rehash the Tools row in `docs/rule-anchors.md`.
