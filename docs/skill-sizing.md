# Skill and agent sizing — what the evidence actually supports

Research pass run 2026-08-07, prompted by a working assumption that the safe
limit for a skill might be ~2,000 words. It is not. This file exists so the next
edit to a skill or agent argues from these numbers instead of re-deriving them.

## The three numbers

| Check                                            | Threshold                          | Basis                                     |
| ------------------------------------------------ | ---------------------------------- | ----------------------------------------- |
| SKILL.md body                                    | **500 lines** (~4,000–5,000 words) | Anthropic official guidance, stated twice |
| Resident tokens (spine + largest on-demand file) | **5,000 tokens** (~3,750 words)    | Claude Code compaction re-attach cut      |
| Whole-tree total                                 | _no published basis_               | local sprawl policy only                  |

Only the first two are externally grounded. A tree-wide word ceiling is a policy
instrument against drift, not an adherence limit — keep it, but do not claim
evidence for it.

## The compaction cliff — the one mechanical rule

From Claude Code's skill-content-lifecycle documentation:

> Auto-compaction carries invoked skills forward within a token budget. When the
> conversation is summarized to free context, Claude Code re-attaches the most
> recent invocation of each skill after the summary, **keeping the first 5,000
> tokens of each**. Re-attached skills share a combined budget of 25,000 tokens.

Consequences, and these are mechanical rather than probabilistic:

- A SKILL.md past ~5,000 tokens (~3,750 words) is **silently truncated from the
  end** in any compacted run. Content near the bottom of a long skill is the
  content most likely to vanish exactly when the run is longest.
- **Files read on demand are tool results, not skill content.** They are
  discarded at compaction and are _not_ re-attached. A spine that says "read the
  phase file when you enter the phase" is therefore the entire recovery
  mechanism — that instruction is load-bearing and must sit in the spine, above
  the truncation line, in every skill built this way.
- More than five invoked skills in one conversation contend for the shared
  25,000-token pool.

`/eng-spec` was at ~3,700 words (~4,900 tokens) before the 2026-08-07 split —
sitting directly on the cut. Its last two phases were plausibly being dropped in
compacted runs. That, not an attention argument, is what justified the split into
a ~230-word spine plus seven phase files.

## Length is not the limit — constraint count is

The instruction-following literature (FollowBench, RECAST, and the multi-turn
follow-ups) measures degradation against the **number of simultaneous
constraints**, not file size:

- Adherence falls monotonically as constraints stack; most models struggle past
  roughly 2–4 simultaneous complex constraints.
- Multi-turn is worse than single-turn on the same constraint set —
  o1-preview measured 88% → 71% between turn 1 and turn 3.
- Nothing in this literature indexes on prompt length in words or tokens.

Chroma's context-rot work points the same way: degradation is **continuous from
short inputs**, not a cliff at some length. A single distractor already hurts.
Models score _better_ on shuffled haystacks than on logically structured ones,
which means "well-organized" does not buy immunity.

Practical read: cutting a skill from 900 words to 700 buys close to nothing.
Cutting the number of rules that must hold at once — by moving a rule into the
one agent that applies it, so it is the agent's only job — buys real adherence.
Displacement beats compression.

## Progressive disclosure — known failure modes

Splitting into on-demand files is the right shape, but it has sharp edges that
are worth designing around:

- **Relative paths do not reliably resolve** from the skill's own directory
  (anthropics/skills#1153). Prefer a path form that has been observed to work in
  the tree it ships in, and verify after any move.
- **Skills get permission-prompted reading their own bundled files**
  (claude-code#15757).
- **Nested references get partially read** — a linked file that links onward is
  often sampled with `head -100` rather than read whole. Keep references one
  level deep.

## Sizing rules that follow

1. Keep the spine well under 3,750 words — under ~1,000 is comfortable and
   leaves room for the largest on-demand file beside it.
2. Measure **resident** load: spine plus the single largest file read at one
   time. That, not the tree total, is what is in context during a run.
3. Put the re-read instruction in the spine. It is the only thing that survives
   compaction on behalf of everything that does not.
4. Split only at real boundaries. Splitting a file in two lowers resident load
   but not tree total, so a split done to buy budget buys nothing.
5. Prefer moving a rule to its owning agent over shortening the sentence that
   states it.

## Sources

- Anthropic — Agent Skills best practices (the 500-line SKILL.md guidance)
- Claude Code docs — skill content lifecycle (the 5,000 / 25,000-token
  re-attach budgets)
- FollowBench, and RECAST — constraint-count vs adherence
- Multi-turn instruction-following evaluations (o1-preview turn-degradation
  figures)
- Chroma Research — "Context Rot: How Increasing Input Tokens Impacts LLM
  Performance"
- anthropics/skills#1153 — relative path resolution
- anthropics/claude-code#15757 — permission prompts on bundled skill files
