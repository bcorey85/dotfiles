# Dispatch Modifiers (+fast / +deep)

Canonical semantics for the `+fast` and `+deep` modifiers accepted by the dispatching skills (`/code`, `/fix`, `/refactor`, `/review`, `/cc`, `/pr-comments`). Skills reference this file instead of redefining the mechanics; each skill's own Modifiers section adds only its when-to-use guidance and any skill-specific modifiers (like `/cc`'s `+show`). `/audit-code` defines its own modifier semantics and does NOT follow this file.

## `+fast`

Pass `model: "haiku"` on every coder/reviewer dispatch the skill makes. This is a deliberate call-site downgrade of a sonnet-pinned agent — the agent-model-guard hook allows it. Use for trivial work: renames, typos, simple one-line changes, quick sanity checks.

## `+deep`

Dispatch the `-deep` variant of each agent (`backend-coder-deep`, `frontend-coder-deep`, `coder-deep`, `code-reviewer-deep`) and **omit `model`** — the variant's frontmatter pins Opus. Never pass `model: "opus"` at the call site; the agent-model-guard hook blocks it (as it does `fable` and `inherit`). Use for complex work requiring deeper reasoning: intertwined systems, security-sensitive changes, subtle migrations.

## Handling rules (all skills)

1. Parse modifiers from args first; at most one of `+fast`/`+deep` applies (if both appear, `+deep` wins — say so).
2. **Strip modifiers from the prompt** passed to subagents — they are dispatch instructions, not task content.
3. When a skill chains to another skill (`/code` → `/review`, `/cc` → `/fix`, `/fix` → `/review`, `/pr-comments` → `/fix`), pass the modifier through in the chained skill's args so the whole pipeline runs at the same depth.
