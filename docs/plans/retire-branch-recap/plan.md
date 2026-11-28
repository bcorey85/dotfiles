# Retire branch-recap: close-branch is the one closing phase and holds the one recap template

Queue item `retire-branch-recap-or-mark-it-legacy-against`. The retire-or-legacy choice is ruled: retire (see
`03-decisions.md`). `/close-branch` already runs the whole close and prints the recap; `/branch-recap` is a second
closing phase with a second recap template.

## Scope

- In: delete `claude/.claude/skills/branch-recap/` and `opencode/.config/opencode/commands/branch-recap.md`; move the
  part of its template that close-branch lacks (the companion-branches step) into `skills/close-branch/SKILL.md`
  Step 6; remove the references in `skills/todos/SKILL.md`, `skills/test-audit/SKILL.md`, `skills/audit/review.md`,
  `scripts/tools/resolve-task-dir.sh`, `scripts/lib/plan_format.py`, `scripts/telemetry/log-scan`,
  `skills/_shared/closing-phases.md`; update `tests/scripts/test_guidance_rules.py`,
  `tests/scripts/test_telemetry_switch.py`, `tests/scripts/test_plan_format.py`.
- Out: herdr scripts, `orchestration.md`, `lane-brief.md`, every CLAUDE.md; the ledger and the agent-evals readers of
  `branch-recap-receipts.jsonl` and of `stage=branch-recap` rows, which keep reading old rows unchanged; history docs
  under `docs/backlog/`, `docs/changes/`, `docs/plans/` and `docs/agent-evals.md`.

## Phase Status

- [x] Phase 1: retire branch-recap and fold its companion-branches step into close-branch (risk: low)

## Phase 1: retire branch-recap and fold its companion-branches step into close-branch

1. Delete `claude/.claude/skills/branch-recap/SKILL.md` and the opencode command `branch-recap.md`.
2. In `close-branch/SKILL.md` Step 6, add the companion-branches check from branch-recap Step 2b with its text kept
   (the `gh pr list` and `git ls-remote` reads, the `no PR` and `not pushed` lines, the `Next:` line rule), and a
   `### Companion branches` section in the recap template. The rest of branch-recap's template is already covered:
   change map, criteria, deferred findings, smoke checklist, open items, still unstaged; test audit is the Close
   pass section; the system map is `/orient`'s on demand.
3. `plan_format.CLOSING_PHASES`: the old four-phase plan's `Recap` title names `/close-branch`. `closing-phases.md`
   says an old plan's Recap phase runs `/close-branch`.
4. `todos` description: the closing phase it is not is `/close-branch`. `test-audit`: description and output lines
   drop the hand-off to `/branch-recap`; its receipt line goes in its report. `audit/review.md`,
   `resolve-task-dir.sh`, `log-scan`: drop `branch-recap` from the caller lists and the documented stage values.
5. Tests: the companion-branches guidance test reads close-branch; the branch-recap receipt test and its path
   variables go; the plan-format tests expect `/close-branch` for `Recap`.

#### Automated Verification

- [ ] `rg -n 'branch-recap' claude/.claude opencode tests` prints nothing.
- [ ] `python3 tests/parallel_tests.py test_guidance_rules.py test_telemetry_switch.py test_plan_format.py` passes.
- [ ] `bash tests/lint.sh claude/.claude/scripts/lib/plan_format.py tests/scripts/test_plan_format.py tests/scripts/test_telemetry_switch.py tests/scripts/test_guidance_rules.py` passes.
- [ ] `bash tests/run.sh` passes.
