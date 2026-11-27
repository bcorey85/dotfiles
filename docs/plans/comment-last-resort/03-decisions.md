# Decisions — comment-last-resort

- **D0** — The user ruled the design on 2026-11-27: one comment rule in every repo, not an own-repos scope. Relayed by agent-evals-c3-owner.
- **D1** — Session ruling, agent-evals-c3-owner, 2026-11-27: the rule goes in coder-core, which every coder loads, and its meter arms run there. code-vocabulary.md keeps a one-line pointer to coder-core. The gate's 3-or-more-line message names coder-core. The code-reviewer rule gets its own scenario. The leftover untracked own-repos plan files stay until the worktree is removed.
- **D2** — Review-loop ask, ruled by this lane 2026-11-27: old lines inside an added run do not count toward the 2-line limit (rejected counting them).
- **D3** — Review-loop ask, ruled by this lane 2026-11-27: a test pins two added lines beside two old ones as passing (accepted).
- **D5** — Branch-review ask, ruled by this lane 2026-11-27: a comment line HEAD lacks counts toward the limit even when an earlier edit added it, so a block cannot be built two lines per edit (accepted). Lines HEAD holds still do not count (D2).
- **D4** — Review-loop ask, ruled by this lane 2026-11-27: blank-separated `#` paragraphs are separate blocks (rejected bridging them).
