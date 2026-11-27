# Code Vocabulary (what may never appear in committed code)

The boundary between private workflow and shipped tree. Read before writing or editing any project source or test file.

Consumers: `spec-criteria`, `code-reviewer` (its opencode port only), and the gates `scripts/gates/stale_citation_gate.py` and `scripts/gates/comment_bloat_gate.py`, which cite this file in their block messages. The coders carry a one-sentence ban of their own and do not load this file.

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

The test: **would a corporate-team reviewer with no knowledge of this workflow accept this line?**

## Comment rule

The comment rule is in `skills/coder-core/SKILL.md`. The rationale, the alternatives, and who decided live in
`docs/plans/` and the ADR, which are not shipped code.

## Sweep before handing back

Diff-check your own committed code against the table before reporting.
