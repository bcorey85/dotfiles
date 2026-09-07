# Code Vocabulary (what may never appear in committed code)

The boundary between private workflow and shipped tree. Read before writing or editing any project source or test file.

Consumers: `coder-core`, `code-reviewer`, `test-authoring.md`, `test-writer`, `eng-spec`,
`/code`, `/refactor`, `/branch-recap`.

## The rule

The planning pipeline (phases, ledgers, specs, friction logs, review loops) is the private operator workflow — none of its vocabulary belongs in committed source or tests.

Banned in `src/`, `tests/`, and every other committed code path — in comments,
docstrings, test names, section banners, fixture names, and **filenames**:

| Banned | Example of the leak |
| --- | --- |
| Phase numbers | `# Phase 6 renders the table`, `tests/contract_phase6.py` |
| Decision ids | `(D8)`, `per D11`, `# D4: returns a list` |
| Plan/doc paths | `See docs/plans/phase-6-static-render/` |
| Pipeline nouns | `ACCEPTANCE-CONTRACT`, `acceptance stub`, `contract_*` |
| Process narration | `Authored before implementation`, `this file is immutable` |
| Agent/author provenance | `written by the coder`, `per the architect`, `the assistant` |
| Ticket keys, unless the project itself uses them in code | `PROJ-142: skip empty` |

The test: **would a corporate-team reviewer with no knowledge of this workflow accept this line?**

## What to write instead

A comment earns its place explaining what **the code cannot say itself**. Say the thing, not where it was decided:

```python
# BAD  — order is a Phase 6 guarantee (D8)
# GOOD — callers rely on name order; sorted() here, not in the widget
```

```python
# BAD  — D4: materialized deliberately, see the decision ledger
# GOOD — materialized: callers index into this and re-read it
```

The rationale, the alternatives, and who decided still matter — they live in
`docs/plans/` and the ADR, which are not shipped code.

## Sweep before handing back

Diff-check your own committed code against the table before reporting. `/branch-recap` re-checks at branch scope.
