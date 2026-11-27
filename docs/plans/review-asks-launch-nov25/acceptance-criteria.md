# Acceptance criteria

Criteria owner: `session` (queue items written by sessions; agent-evals-74 rules on cuts and rewordings).

- **AC1** — full_check with a --log path whose parent folder does not exist creates the folder and writes the log; before the fix it raised FileNotFoundError. (Phase 1)
- **AC2** — A /review launch from a session that holds a plan passes the plan path: with no --plan flag the launch reads the plan from the repo's code-phase record and writes it into the prompt header. (Phase 2)
- **AC3** — The reviewer brief of a run with a plan lets the reviewer open the plan's 03-decisions.md and says a question a recorded ruling answers is not an ask. (Phase 2)
- **AC4** — The inline-interpreter deny text leads with the scratch-script route and names the session's scratchpad folder when it exists. (Phase 3)
- **AC5** — `bash tests/run.sh` passes.
