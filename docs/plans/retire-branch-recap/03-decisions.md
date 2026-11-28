# Decisions

- Retire, not legacy: ruled by agent-evals-c3-owner on 2026-11-27, under the user's away-trip ask (agent-evals
  decision 132). No branch-recap use after October; close-branch replaced it.
- An old four-phase plan's Recap phase maps to `/close-branch`, not to nothing: eval fixture plans under `~/dev/evals`
  still carry an open Recap phase, and a title with no skill would fail plan check there. Ruled by this lane,
  2026-11-27.
- The companion-branches step moves into close-branch with its wording kept, so it is a move, not a reworded rule,
  and needs no rule-meter arms; the closing-phases.md line only renames the skill the retired phase runs. Ruled by
  this lane, 2026-11-27.
- Telemetry readers stay as they are: the ledger, `scrub_stream.py`, `deferred_followthrough.py` and
  `work-intake.sh` in agent-evals keep reading old `branch-recap` rows; only the writer goes. Ruled by this lane,
  2026-11-27.
