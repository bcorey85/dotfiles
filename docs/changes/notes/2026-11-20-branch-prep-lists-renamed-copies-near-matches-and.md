---
type: "Change"
change_type: "added"
title: "Branch-prep lists renamed copies, near matches and the nearest other functions of each added function"
description: "refactor_flow branch-prep compares each changed Python or TypeScript function with every function in the repo once names, attribute names and literals are stripped, and lists the nearest other functions of each added function."
generated: {"by": "process:coder", "at": "2026-11-20T18:30:00-06:00"}
seq: 2
kind: "fix"
components: ["skill/refactor", "agent/smell-reviewer", "script/refactor-flow", "script/shape-clones"]
evidence: ["branch-refactor-finds-renamed-near-clones-and"]
watches: []
test: "tests/scripts/test_shape_clones.py::PythonShapeTest::test_a_one_token_variant_is_a_near_match_pair"
asked: ""
proof: []
unmeasured: ""
---

## Change

`shape_clones.py` reads function bodies (Python with `ast`, TypeScript and TSX from `tree-sitter parse --xml` with nvim's grammar) and reduces identifiers, attribute names and literals to placeholders; keywords and operators stay. A changed function whose body equals another function's is a renamed-copy pair; one within one token edit per 20 tokens is a near-match pair. For each function the branch added, the catalog lists up to three other non-test functions by token-pair overlap (a changed function stays a candidate; only functions the branch added are left out). The smell-reviewer text names the candidate kinds; the output asks no question (see Result). A missing CLI or grammar, or XML that does not parse, is a note. `--head` skips the pass with a note.

A script cannot decide whether a domain-named function is generic, so the generic-helper-candidate criterion is met by the catalog entry, not a script verdict (ruling recorded in the plan's deviations).

## Evidence

Queue item `branch-refactor-finds-renamed-near-clones-and`.

## Result

Tests in `test_shape_clones.py`, `test_sequence_similarity.py` and `test_refactor_flow.py`; the pass takes about 2 s on the dotfiles repo.

Rule-meter scenario NC01 (smell-reviewer, opus, plant `formatBudget` copying `formatCents`, catalog block in the task in both arms, the two questions cut in the off arm), 2 runs per cell: on 6/6 COMPLIED, off 6/6 COMPLIED, at every level (supportive, neutral, competing). Graded by section, all 12 reports name `formatCents` under `### Fix`. The catalog alone reaches the ceiling on a renamed copy, so the does-a-helper-already-do-this question was cut.

NC02 and NC03 (plant `getMatterForInvoice`, a find-by-key under a domain name; NC02's repo also holds a generic `findByKey` and its catalog lists it, NC03's holds none; the off arm cuts only the generic-operation question), 4 runs per cell: NC02 on 12/12, off 12/12; NC03 on 12/12, off 12/12 COMPLIED, all graded by section under `### Fix` or `### Ask`. Null result: the smell-reviewer flags the generic operation under a domain name without the question, so it was cut too. The catalog ships with no question.

## Watch

None.

## Back-out

Revert the commit.
