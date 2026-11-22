---
type: "Change"
change_type: "fixed"
title: "plan check and verify-prep read the criteria file through one function"
description: "A criteria file that plan check --final passes now also passes verify-prep, because both read it through plan_format.parse_criteria_file; a numbered or unbolded list fails at write time, not at branch end."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T15:13:21-06:00"}
seq: 23
kind: "fix"
components: ["script/verify-prep", "script/plan-format", "script/plan-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_verify_prep_shared_rules.py::CriteriaGrammarTest.test_plan_check_final_refuses_a_numbered_list_verify_prep_refuses"
asked: ""
proof: []
unmeasured: "No intake number reads it; the queue item that reported it is the evidence."
---

## Change

`parse_criteria_file` and its id regexes moved from `review/verify_common.py` into `lib/plan_format.py` (raising PlanFormatError); verify_common wraps it to raise VerifyError. `plan_format.criteria_file_failure` runs it and reports a file with no id, and `missing_criteria_failure` (plan check --final, /code start) now calls it. verify-prep keeps its own empty-file stop, worded by `no_criteria_message`.

The grammar also reads one optional lower-case letter after the number (`AC12a`): the three id regexes, `AC_REFERENCE` (so `criterion_ids_in`, verify-log's covered ids and the criteria drift check read it), `CRITERION_LINE` (no longer upper-cases the id), verify-prep's id sort (`plan_format.criterion_id_order`, AC12 before AC12a) and the two comment gates' `AC<n>` markers. A two-letter or upper-case suffix is still refused.

## Evidence

A plan with a numbered criteria list passed plan check --final at every phase and stopped verify-prep at branch end (exit 2). plan check only tested that the file was non-empty.

## Result

Test for the suffix: `tests/scripts/test_verify_prep_shared_rules.py::CriteriaGrammarTest.test_a_letter_suffixed_id_passes_plan_check_and_verify_prep`. Over the 158 distinct acceptance-criteria.md files under ~/dev and ~/agent-ledger-dev, 8 are refused, all eval-bench fixtures with no id or a malformed line; the agent-ledger plans with AC12a, AC20b and AC7b pass.

New tests fail on the old tree (no `criteria_file_failure`, plan check exits 0 on a numbered list) and pass now.

## Watch

None.

## Back-out

Revert the commit: the parser returns to verify_common and plan check goes back to the non-empty test.

