# Lane: usage — token burn from local transcripts

Ground truth for "where are my tokens going": real per-message `usage` fields
from `~/.claude/projects/**/*.jsonl`, aggregated by `ccusage-breakdown`
(scripts package, on PATH).

## Run

1. **Window**: from the lane arguments ("today", a date, a range, "this week").
   Default: **last 7 days**. Compute the literal dates yourself and pass both:
   `ccusage-breakdown <start> <end>` (YYYY-MM-DD). Output is compact — run it
   directly and read it.
2. The report sections: total MB + session/subagent counts, sessions by
   project, **Token Usage (day × model)**, MCP tool usage, top-10 heaviest
   conversations with their opening prompts.

## Interpret

- **New In** (uncached input + cache creation) and **Output** are what drain
  plan limits; **CacheRd** is ~10% weight. Rank burn by `New In + Output`.
- Weight by model tier: opus/fable-class messages drain limits several times
  faster than sonnet-class per token. A modest fable row can outweigh a big
  sonnet row.
- **main vs subagents split**: fat main-session numbers → the orchestrator
  (model choice, always-loaded context, long sessions) is the cost center;
  fat subagent numbers → the dispatch pipeline (fan-out per task) is.
- Many small sessions with high New In → per-session overhead (system prompt,
  CLAUDE.md, skill descriptions). Few sessions with high Output → long agent
  loops.
- Heaviest conversations list is where to name names — cite 1–3 with their
  opening prompts.

## Report (≤10 lines)

Top burn driver (day × model, with numbers) → main-vs-subagent verdict →
1–3 heaviest conversations → ONE lever (the single highest-impact change:
model routing, `+fast`, session hygiene). Note this is this machine's data
only; other machines need the same run locally.
