# Decisions

1. ENV against RED: a check that could not run reads ENV; a check that ran and failed reads RED. Ruled by the lane under the orchestrator agent-evals-74's brief, 2026-11-26.
2. "Exit 1 from any check reads RED" holds for every check except a search ban, where no match (exit 1) is the pass. Taking it literally would break every ban. Lane ruling, 2026-11-26.
3. A run with a runner summary ran tests: an `is not set` or refused-connection line in it stays RED. Lane ruling, 2026-11-26.
4. Closing-phase checks are listed as CLOSING and not run: their skill runs them after the work exists. Lane ruling, 2026-11-26.
5. The memory cap already wraps every dry-run command (commit 285a68979, on master since 2026-11-25); the bench runs show the cap ran. No change. Lane ruling, 2026-11-26.
6. From origin/fix/criteria-dry-run-verdict: its shared `item_verdict` and search tests are already on master. Nothing else taken.
