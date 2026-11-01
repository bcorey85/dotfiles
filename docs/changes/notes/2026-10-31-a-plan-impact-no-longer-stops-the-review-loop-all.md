---
type: "Change"
change_type: "changed"
title: "A plan impact no longer stops the review loop; all show once at the end"
description: "A review keeps fixing past a plan question instead of stopping and repeating its first round, and the user hears about plan impacts once, after the result."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T15:15:30-05:00"}
seq: 6
kind: "user-rule"
components: ["script/review-loop-script", "script/review-fix", "script/handback", "script/plan-format", "agent/review-loop", "skill/review", "skill/fix", "skill/code"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-31: dont ever tell me about plan impact stuff until the end 99% of the time i feel like i just say 'k adjust the plan'. we shouldnt be wasting my time or llm turns bailing out of the current turn like its some critical event"
proof: []
unmeasured: ""
---

## Change

The scripted review loop no longer stops on a plan impact. `review_loop_script.py` drops the plan-change stops and records each impact in a new packet key, `plan_impacts`:

- An impact that changes no acceptance criterion is adopted by rule, and its fix runs in the same round.
- A reviewer's impact that changes an acceptance criterion is held: its fix stays unapplied.
- A coder's `plan impact: yes` is recorded, and the loop goes on. When it changes an acceptance criterion it is held
  too, but the coder's edits are already in the tree (`applied`), so keeping the plan means reverting them.
  Every finding the coder skipped, or left unchanged, in a round whose impact is held stays open in
  `findings_remaining`, not in `skipped_fp`, until a later round fixes it. Beside an adopted or toolkit impact, a skip
  is a plain skip.
- Only a held impact (not adopted, any cause but `toolkit`) keeps the review dirty. A toolkit-cause impact is only
  reported.
- A `plan_impact: RESOLVED` handoff turns the plan-marked items the ruling or a carried finding names into plain fixes.

`review_fix.py packet` prints the impacts once, after the review result. Adopted ones print as `## Plan Deviations` lines with no question. A toolkit-cause impact prints as a toolkit fault. Held ones get one closing question. `decide adopt` re-dispatches once with the impact resolved. `decide keep` records the ruling and writes a `plan-ruling` row to the hand-back store, so the commit gate counts the review as clean. `handback.false_clean_reason` keeps the review dirty while a held impact has no ruling.

The plan-change mark (`lib/plan_format.py`) now reads `file:13`, `file:13-14`, `file:13–14` and `file:58-101,139-147` the same, so the outcome no longer depends on how a reviewer wrote a line number.

`/code` no longer has a `plan-impact` route, because the loop never returns that status. When a converged packet holds a held impact, `/code` puts it on the phase-end list, writes `plan_impact: RESOLVED: deferred to phase end by the session, <date>: <summary>` into its handoff file, and runs `review_fix.py defer <handoff file>`, which records the ruling so the commit gate clears.

Known gap. Counting plan impacts per run in the intake is a separate queue item.

## Evidence

On the bench runs, the stop came down to whether a reviewer wrote a line range, in both arms. A run that stopped left every fix undone and repeated the first review round. A run that did the fixes and asked at the end passed all 13 checks.

## Result

`tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_plan_impact_ask_never_stops_the_loop_and_the_round_s_fixes_still_run` and `...::test_a_plan_impact_ask_reads_the_same_with_a_line_range_or_a_list_of_ranges` fail before the change and pass after. Handback and review_fix tests cover held, adopted, toolkit, adopt and keep. Targeted suites pass.

## Watch

None. The intake does not record plan-impact stops yet; the follow-up item adds the count.

## Back-out

Revert the `plan_impacts` routing in `review_loop_script.py`, `review_fix.py` and `handback.py`, and restore the plan-change stops.
