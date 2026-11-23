# Plan review round 1, shard b (Phases 5-9)

VERDICT: NEEDS CHANGES (3 blocker, 8 gap)

BLOCKER Phase 7 §1 + Phase 8 §3 (D7): the rule_meter.py edits go past the D7 sign-off (one PLANTS entry, one grade() branch). Plan needs 4 plants (derivable, underivable, PI01's, BL01's) and 3 grade() branches. Plant bodies live in rule_meter.py (PLANTS at :2365); rule_meter_checks/ has no __init__.py and only bin/ is on sys.path (:57). PI01's plant also needs a plan or criteria file for code-reviewer to compare against.

BLOCKER Phase 6 §1: RF03/RF05 rule_text is not in review-fork-run.md today (RF01 is). Copies fail on missing text. Plan never says to set each W copy's rule_text to the new bullet text, and schedules RF01's off arm after the reword instead of before.

BLOCKER Phase 5 §2: `claude/.claude/skills/adr/adr-template.md` does not exist; the real file is `skills/_shared/adr-template.md` (adr_flow.py:44, test_adr_flow.py:21,37). Folding skimmable into it leaves a one-loader _shared file (AC5 still fails); moving it changes two files Phase 5 does not list.

GAP Phase 5 §3: escape-ratchet is also cited by scripts/telemetry/log-escape, scripts/review/verify-log, skills/refactor/scripts/refactor_flow.py; code-vocabulary also by scripts/gates/comment_bloat_gate.py. New consumer lists omit 4 script loaders; "lists exactly the consumers" cannot pass.

GAP Phase 5 §3 criterion: weak-pointer regex also matches eng-spec/phases/6b-review.md:50, which no phase edits (7 sites, plan names 6).

GAP Phase 7 §3: reviewer-calibration:78-80 says ask is not the plan-impact channel; Phase 7 puts the PLAN-IMPACT placeholder under code-reviewer `### Ask` and PI01 grades COMPLIED only there. Contradiction.

GAP Phase 5/6/7 §5: "no port" claims false: opencode has test-reviewer.md, goal-blind-researcher.md (:29 repair loop), spec-research.md, code-reviewer.md (:115 PLAN-IMPACT line). AC10 unowned for them.

GAP Phase 8 §4: R's live rule (code-reviewer:49, prior-art search) plus the supportive suffix can make the off arm flag KNOWN_SKILLS anyway; AC7's off-arm-quiet has no fallback.

GAP Phase 8 §2-3: second_owner_mutation.py is a hidden-mutation subprocess, not a report grader; no `expect` key reader exists; quiet-case precedent is a separate `no_false_alarm_*` detector in rule_meter_fixture.DETECTORS (grade() :1477). Detector shape and quiet route are ambiguous.

GAP Phase 5 §4: CU01's detector grades the input-shape rule, which is in test-intent-reviewer:53 only, not in test-reviewer:45 (the cut text). CU01 cannot fail.

GAP Phase 8 criterion: `python3 -m unittest /abs/path.py` fails with ModuleNotFoundError from the worktree; needs discover or cwd bin/, plus the memory cap.

NIT: anchor rows: goal-blind-researcher is :156, spec-research :159; test-audit and adr-template have no rows.
NIT: line refs go stale across phases (coder-core :97 after Phase 6; code-reviewer "after line 51" after Phase 7).
NIT: `--rule` takes one id; "CU01 and CU02", "RF01W, RF03W, RF05W", "PI01 and BL01" run only the first.
NIT: 12 uncapped test commands; the memory-cap hook denies them.
NIT: coder-core:43 after the cut loses the antecedent of "it" and "one".
NIT: Phase 6 §3 "lines 107 and 110 point to it or are cut" leaves the choice open.
NIT: finding-log Emit :24 still carries `[source=...]` after :40-43 are dropped.
NIT: after re-pointing to master, DL01/DL02/RF*W/CU02 cannot build until merge; CU01, PI01, BL01 point at deleted text and never build again.
NIT: Phase 8 sub-bullet reaches smell-reviewer through its Step 3 rg slice; sweep does not mention it.
