# Decisions

Rulings by the orchestrating session agent-evals-74, 2026-11-25, by SendMessage. Criteria owner: `session`; agent-evals-74 rules on cuts and rewordings.

1. **Drop the asks-done item** (agent-evals-74, 2026-11-25). `asks-done --by session` exists since 999f519ec (2026-11-11) and is tested in `tests/scripts/test_review_fix_ask_ruler.py`. It refuses only `user_only` asks, which name user-owned criteria or an approval-only file edit; the acceptance-criteria rule keeps those for the user. agent-evals-74 closes the queue item.
2. **Item 1 test reworded** (agent-evals-74, 2026-11-25). The test checks that the launch carries the plan into the prompt header, and that the reviewer brief opens `03-decisions.md` with the ruled-question line (AC2, AC3). The brief line is a new prompt rule: run rule-meter if a scenario fits, else list it as unmeasured in the change file and keep it on the branch.
3. **Item 4 replay unmeasured** (agent-evals-74, 2026-11-25). The 9 of 10 replay is not run under this load; the change file lists it as unmeasured and agent-evals-74 queues the replay separately.
