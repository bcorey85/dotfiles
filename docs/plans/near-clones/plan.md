# Near clones: renamed copies, near matches and nearest helpers in branch-prep

Ticket: queue item `branch-refactor-finds-renamed-near-clones-and`. Branch-prep compares each changed function with
every function in the repo once names and literals are stripped, and lists the closest existing helpers of each added
function for the smell-reviewer. No model call. Scripts live in `claude/.claude/skills/refactor/scripts/` and
`claude/.claude/scripts/lib/`; tests in `tests/scripts/`, paths from `tests/scripts/toolkit_paths.py`.

## Scope

- In: new `skills/refactor/scripts/shape_clones.py`, new `scripts/lib/sequence_similarity.py`,
  `script_utils.repo_file_paths`, the branch-prep call in `refactor_flow.py`, the refactor SKILL.md step 3a and the
  smell-reviewer text (claude and opencode copies) with their rule-anchor rows, their tests.
- In: rule-meter on/off arms for the two shape questions (scenario NC01 in `~/agent-evals/bin/rule_meter_scenarios.json`, ruling (a) by agent-evals-5e, 2026-11-20).
- Out: audit-prep (jscpd only).

## Phase Status

- [x] Phase 1: branch-prep lists renamed-copy and near-match pairs and the nearest helpers of each added function (risk: medium)

## Phase 1: branch-prep lists renamed-copy and near-match pairs and the nearest helpers of each added function

Python bodies are read with `ast`; TypeScript and TSX bodies from `tree-sitter parse --xml` with nvim's grammar.
Identifiers, attribute names and literals become placeholders; keywords and operators stay. A changed function equal to
another function once normalized is a renamed-copy pair; within one token edit per 20 tokens is a near-match pair. For
each added function the pass prints its nearest non-test helpers (questions cut, see Plan Deviations). A missing CLI or grammar is a note.
`--head` skips the pass with a note. Estimated diff: about 450 lines of code and 400 of tests.

**File**: `claude/.claude/skills/refactor/scripts/shape_clones.py`
**Test**: `tests/scripts/test_shape_clones.py`

## Testing Strategy

- Python and TypeScript fixtures: a renamed copy, a one-token variant (`<` against `<=`), a domain-named lookup whose
  nearest catalog entry is the generic helper.
- `python3 tests/parallel_tests.py test_shape_clones.py test_sequence_similarity.py test_refactor_flow.py` passes;
  `bash tests/run.sh` passes. The pass runs under 10 s on this repo.

## Plan Deviations

- Done-when "flags a domain-named function with a generic body as a generic-helper candidate by analysis of
  domain-specific attributes or calls" becomes: the script prints the catalog nearest-neighbours and the two questions
  for the smell-reviewer to judge, and the criterion is met by the catalog entry plus the question, not a script
  verdict; ruling by agent-evals-5e citing the user's ruling that a script cannot cover this, 2026-11-20; Ticket
  `branch-refactor-finds-renamed-near-clones-and`.
- AC3 loses "asks the smell-reviewer whether an existing helper already does this and whether it is a generic
  operation under a domain name": rule-meter NC01 (on 6/6, off 6/6), NC02 (12/12 each arm) and NC03 (12/12 each arm)
  show no effect from either question, so both are cut and the catalog ships alone; ruling by agent-evals-5e
  ("cut question 1 ... ship question 2 only if on beats off; else cut it and record the null"), 2026-11-20.
- Diff size: estimate about 450 lines of code and 400 of tests; real about 603 of code and 969 of tests (1.85x total);
  reported to agent-evals-5e at hand-over; ruling by session, 2026-11-20.
- Scope gains the two inline `git ls-files` listings in `scripts/review/review_loop_ruled.py` and
  `review_loop_intake.py`, switched to `script_utils.repo_file_paths` (branch review finding); ruling by
  agent-evals-5e, (a), 2026-11-20.
