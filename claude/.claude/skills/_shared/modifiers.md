# Dispatch Modifiers (+fast / +deep)

Semantics for `+fast` / `+deep` (dispatching skills reference this). Skills add only when-to-use + skill-specific modifiers.

## `+fast`

Pass `model: "haiku"` on every dispatch (deliberate downgrade; the agent-model-guard hook allows it). Trivial work only.

## `+deep`

Dispatch the `-deep` variant of each specialist reviewer (security, perf, smell, complexity) and **omit `model`** (frontmatter pins Opus; call-site `opus` is hook-blocked). `coder` and `code-reviewer` already pin Opus: dispatch them as is, with no `model`. Complex work only.

## Handling rules (all skills)

1. Parse modifiers from args first; at most one of `+fast`/`+deep` applies (if both appear, `+deep` wins — say so).
2. **Strip modifiers from the prompt** passed to subagents — they are dispatch instructions, not task content.
3. When chaining skills, pass the modifier through so the pipeline runs at one depth.
