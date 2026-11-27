# Plan — comment-last-resort

Criteria: `acceptance-criteria.md`. Decisions: `03-decisions.md`.

## Phase 1 — gate and rule text

- `claude/.claude/scripts/gates/comment_bloat_gate.py`: a run of at most 2 added non-kept comment lines passes; a run of 3 or more is blocked, and the message points architecture prose to the repo's architecture docs and names `skills/coder-core/SKILL.md`.
- `tests/scripts/test_comment_bloat_gate.py`: pin 1, 2 and 3 line blocks; `tests/scripts/test_review_fixes.py` blocking cases move to 3-line blocks.
- `claude/.claude/skills/coder-core/SKILL.md`: the comment rule bullet under "Readability comes first".
- `claude/.claude/skills/_shared/code-vocabulary.md`: the old guidance section becomes a pointer to coder-core.
- `claude/.claude/agents/code-reviewer.md` and the opencode port: flag each added comment a busy engineer new to the code would not need; the fix is to delete it.

## Phase 2 — measurement and records

- agent-evals rule meter: scenario CC01 (coder, coder-core) and SR01 (code-reviewer), on and off arms.
- Change files with the per-arm counts; rule-anchors rows relinked.

## What We're NOT Doing

- No per-repo scope for the gate (the user ruled one rule in every repo).
