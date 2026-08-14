# Code Vocabulary (what may never appear in committed code)

Single source of truth for the boundary between the private workflow and the
shipped tree. Read this before writing or editing any file under a project's
source or test directories.

Consumers: `coder-core`, `code-reviewer`, `test-authoring.md`, `test-writer`, `eng-spec`,
`/code`, `/refactor`, `/branch-recap`.

## The rule

The planning pipeline — phases, decision ledgers, specs, friction logs, review
loops — is **the operator's private workflow**. It is not part of the product,
it is not visible to the team that reviews this code, and it means nothing to
the person who opens the file in two years. None of its vocabulary belongs in a
committed source or test file.

Banned in `src/`, `tests/`, and every other committed code path — in comments,
docstrings, test names, section banners, fixture names, and **filenames**:

| Banned                                                   | Example of the leak                                          |
| -------------------------------------------------------- | ------------------------------------------------------------ |
| Phase numbers                                            | `# Phase 6 renders the table`, `tests/contract_phase6.py`    |
| Decision ids                                             | `(D8)`, `per D11`, `# D4: returns a list`                    |
| Plan/doc paths                                           | `See docs/plans/phase-6-static-render/`                      |
| Pipeline nouns                                           | `ACCEPTANCE-CONTRACT`, `acceptance stub`, `contract_*`       |
| Process narration                                        | `Authored before implementation`, `this file is immutable`   |
| Agent/author provenance                                  | `written by the coder`, `per the architect`, `the assistant` |
| Ticket keys, unless the project itself uses them in code | `PROJ-142: skip empty`                                       |

The test: **would a reviewer on a corporate team, with no knowledge of this
workflow, understand and accept this line?** "Phase 6" fails — it is a private
marker with no referent in the repo. So does a docstring arguing for its own
authority.

## What to write instead

A comment earns its place by explaining something **the code cannot say
itself** — a workaround, a surprising API, an invariant not visible locally.
Say the thing, not where the decision was recorded:

```python
# BAD  — order is a Phase 6 guarantee (D8)
# GOOD — callers rely on name order; sorted() here, not in the widget
```

```python
# BAD  — D4: materialized deliberately, see the decision ledger
# GOOD — materialized: callers index into this and re-read it
```

The rationale, the alternatives, and who decided still matter — they live in
`docs/plans/` and the ADR, which are not shipped code. Prose that teaches
belongs in the conversation, where it lands once, rather than in a file, where
it rots and every future reader pays for it.

## Sweep before handing back

Any agent that wrote or edited committed code checks its own diff for the table
above before reporting. `/branch-recap` re-checks at branch scope, since a leak
is cheapest to remove before the PR and most embarrassing after it.
