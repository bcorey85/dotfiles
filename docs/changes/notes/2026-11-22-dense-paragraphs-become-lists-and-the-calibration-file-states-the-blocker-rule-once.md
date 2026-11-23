---
type: "Change"
change_type: "changed"
title: "Dense paragraphs become headed sections and one-branch lists, and the calibration file states the blocker rule once"
description: "review-fork-run gets six headings and a bulleted Resume; coder-core's verify paragraph, 6b-review step 19b, 5-decisions step 14, goal-blind-researcher step 3 become lists, spec-research's search rules become a list and its edit rule stays a paragraph; reviewer-calibration merges self-check question 2 into question 3, drops question 5 and one rationale paragraph; the opencode goal-blind-researcher port gets the same list."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T19:00:00-06:00"}
seq: 28
kind: "fix"
components: ["shared/review-fork-run", "skill/coder-core", "shared/reviewer-calibration", "skill/eng-spec", "agent/goal-blind-researcher", "agent/spec-research"]
evidence: ["rule meter", "judgment"]
watches: []
test: "tests/scripts/test_toolkit_prose_facts.py::ToolkitProseFactsTest::test_goal_blind_researcher_and_opencode_port_both_list_the_repair_loop_branches"
asked: ""
proof: []
unmeasured: "Every layout split (review-fork-run headings, coder-core verify list, 6b-review step 19b, 5-decisions step 14, goal-blind-researcher step 3, spec-research search list); the 'Answer that stop:' to 'Answer the stop you resume:' reword; the line RF03 graded, whose rule_text is not in the file, and the line RF05 graded, whose scenario is retired; the cut of the calibration rationale paragraph, of self-check's blocker-reproduction sentence (old question 2) and of question 5 with its scoring line, and the merge of question 2's reachability clause into question 3."
---

## Change

review-fork-run has the headings The run folder, Launch, Reviewers, The packet's ACTION lines, Ending the run hands back and Resume. Resume is a bullet list. coder-core's verify paragraph is a list after "Otherwise:". reviewer-calibration states the blocker rule once, in Disposition, and loses the rationale after the plan-impact sentence; self-check's blocker-reproduction sentence (old question 2) is cut, question 2's reachability clause moves into question 3, and question 5 and its scoring line are cut because Disposition already states them (the blocker-likelihood paragraph and the claim-not-lever paragraph). 6b-review step 19b, 5-decisions step 14, goal-blind-researcher step 3 are lists with one rule per item. spec-research's search rules are a list with one rule per item; its edit rule stays a paragraph. The opencode goal-blind-researcher port carries the same step 3 list; the opencode spec-research port has no dense search paragraph, so it is unchanged.

## Evidence

Rule-meter arms on the `--by session` / `--by user` Resume rule (the scenario graded the first asks-done ruler flag), run on the worktree text, supportive, neutral and competing suffixes, one run per cell:

- RF01B before the edit, on 2/2 (100%), off 1/1 (100%); 3 cells had no asks-done call (NO_TEST).
- RF01W after the edit, on 1/1 (100%), off 1/1 (100%); 4 cells had no asks-done call (NO_TEST).

Per-arm counts: RF01B on COMPLIED 2, NO_TEST 1; RF01B off COMPLIED 1, NO_TEST 2; RF01W on COMPLIED 1, NO_TEST 2; RF01W off COMPLIED 1, NO_TEST 2. The sample is one run per cell and mostly NO_TEST, so the arms show no loss and no gain.

## Result

Each listed paragraph is a list with one branch per item, and the blocker rule has one owner.

## Watch

None.

## Back-out

Revert the commit.
