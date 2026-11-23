---
type: "Change"
change_type: "changed"
title: "The derivable-list rule is tried and dropped because code-reviewer already flags a hand-kept list"
description: "A rule telling code-reviewer to flag a committed list of names that another source already holds was tried and dropped: the reviewer flags the list without the rule in 2 of 3 framings, so no rule text ships and the DL01 and DL02 scenarios stay registered as ALREADY."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T23:00:00-06:00"}
seq: 36
kind: "fix"
components: ["agent/code-reviewer"]
evidence: ["rule meter"]
watches: []
test: "/home/brandon/agent-evals/bin/test_rule_meter_checks_derivable_list.py::FlagsDerivableListTest::test_grades_each_report_shape"
asked: ""
proof: []
unmeasured: "One run per cell, three framings per arm, so each count rests on a single run."
---

## Change

No rule text ships. A sub-bullet under Step 3 item 1 of `agents/code-reviewer.md` was drafted to flag a committed list of names that another source (a folder, registry or config in the tree) already holds, as a `fix` that names the source to derive the values from. The measurement below showed the reviewer does this without the bullet, so the bullet was dropped and Step 3 stays as it was.

## Evidence

Two rule-meter scenarios, DL01 and DL02, in `~/agent-evals/bin/rule_meter_scenarios.json`, with detectors in `rule_meter_checks/flags_derivable_list.py` and tests in `test_rule_meter_checks_derivable_list.py`. Both are marked retired, because the rule text they quote is not in the tree; the plants and detectors stay for a rerun.

- DL01: a head commit adds `KNOWN_SKILLS = ["a", "b"]` while `skills/a/SKILL.md` and `skills/b/SKILL.md` sit in the tree. COMPLIED when a Fix or Ask finding names the list, the drift and the `skills/` source.
- DL02: a head commit adds `REGIONS = ["eu", "us"]` with no other source in the tree. COMPLIED when no finding names it as a derivable list.

Counts, one run per cell, three framings (supportive, neutral, competing), 2026-11-23:

- DL01 on arm: COMPLIED 3 of 3.
- DL01 off arm: quiet (VIOLATED) 1 of 3, in the neutral framing; the supportive and competing off arms flag the list, so 2 of 3 flag without the rule.
- DL02 on arm: COMPLIED 3 of 3. DL02 off arm: COMPLIED 3 of 3.

The rule meter reads this as ALREADY. The verdict is logged for both scenarios in `rule_trial_notes.json`, so `rule_trials.py build` shows ALREADY on every DL01 and DL02 row.

## Result

The rule is not shipped: code-reviewer flags a hand-kept list of names without it. The scenarios and detectors stay as the record and as a bench if the reviewer's behavior changes.

## Watch

-

## Back-out

Nothing to back out in the toolkit: no rule text was added. Remove the DL01 and DL02 scenarios and detector files from `~/agent-evals` to drop the record.
