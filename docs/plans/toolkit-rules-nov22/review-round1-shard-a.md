# Plan review, round 1, shard A (plan-reviewer, 2026-11-22)

DUCK     Phase 0: adds a stub module `bin/rule_meter_checks/tool_call_detectors.py` (three functions that raise NotImplementedError), an import line plus three if/return dispatch pairs in `grade()`, and a test file whose three tests are expected to fail. All edits go into `~/agent-evals/bin`.
DUCK     Phase 1: adds the Agent `model` bullet under `### Delegation` in this worktree's orchestration.md. Appends scenario AM01 with its root set to this worktree. Fills `detect_agent_model_allowed` and its table tests. Runs AM01 once per cell (6 opus runs), then more neutral runs. Writes a change note, a finding and the rehashed 2ebac3a6 anchors row.

BLOCKER  Phase 0 / Phase 1, agent-evals edits  No phase creates the `toolkit-rules-nov22` branch, or a worktree for it, before the first edit in `~/agent-evals`.
         Evidence: every path in Phase 0/1 is `/home/brandon/agent-evals/bin/...` and every command is `python3 ~/agent-evals/bin/...`. `git -C ~/agent-evals worktree list` shows `/home/brandon/agent-evals d2fa6c3b [bench-base]`, and `git status` there shows ` M QUEUE.md`, ` M queue/index.md`, `?? queue/criteria-dry-run-...` (another session's uncommitted work; the plan's Constraints say never to touch them). The only branch step is in the lane-end paragraph (spec.md:472): "the agent-evals commit on branch `toolkit-rules-nov22`". Phase 0 calls itself "Committable".
         Reading: either way a coder ships something wrong. Reading 1: commit Phases 0 and 1 where the checkout already is, which is bench-base, the branch the ticket items were claimed on. That conflicts with AC18 and D8. Reading 2: run `git checkout -b toolkit-rules-nov22` in the shared `~/agent-evals` checkout. That switches the branch under the orchestrating session's own work tree and its dirty QUEUE files. Every other agent-evals lane has its own worktree (`agent-evals-asks-rulings-2`, `agent-evals-build-queue-fixes`, ...). The plan needs a Phase 0 step that names the worktree path (or the branch) and repoints every `~/agent-evals/bin` path and command at it. The stale-file check in the Constraints (`git -C ~/agent-evals status bin/`) has to point there too.

BLOCKER  Phase 1 §4, meter runs  `--runs 7` "after the first" gives 7 runs per neutral arm, not 8. The `structured` proof floor is 8, so the change file cannot pass `--check` unless the finding claims a wrong count.
         Evidence: plan: "run the neutral level to 8 per arm (`--level neutral --runs 7` after the first; Q4)". `rule_meter.py:2681` reads `"--runs", ... help="runs per cell"`. `pending_runs` (:1666-1681) does `missing = runs - len(used)`, so `--runs` is the total a cell should reach, not how many runs to add. `build_changes.py:56-57` says "runs_per_arm is at least the floor of the kind: PROOF_FLOORS, 8 for structured", and Q4/Phase 1 call for "`runs_per_arm` 8".
         Reading: the smoke leaves one run in each neutral cell. `--runs 7` then adds 6 per arm, so each arm ends at 7. The finding would need `runs_per_arm: 7`, which fails `Change-file-verified`, or `8`, which is false. The correct command is `--level neutral --runs 8` (14 more runs, 20 opus runs in total). Spec.md:430 (Phase 3) and Q4 ("16 opus runs per item after the smoke") give a third, different count. All three need to agree.

GAP      Phase 1 Success Criteria, "Line-matches-hook"  This criterion cannot fail, and the External Contracts promise of a test against the hook has no owner.
         Evidence: criterion: "the line names no value the hook denies as allowed — `rg -n -c 'set .sonnet. or .haiku.' ... finds 1 line (presence)`". External Contracts (spec.md:89): "Phase 1's test asserts the line names only values the hook passes."
         Reading: the rg only checks that the coder's own text is there. It passes for any line that contains those words, whatever else the line says. Nothing ties the line to `agent-model-guard.sh` (fork passes any model; opus and inherit are denied case-insensitively; an empty model passes only when an agent file pins one; web-fetch is rewritten to haiku). AC11 ("states exactly what the model hooks ... enforce, and no more") therefore has no check that can fail. One example of a check that could: feed the hook the values the line names (sonnet, haiku, an empty model with a pinned agent file) and the ones it says are denied (opus, inherit), using the existing hook-test pattern.

GAP      Phase 1 / AC10 second sentence  No phase owns AC10's "A headless run that launches a general-purpose agent sends no opus pin", and item 3 has no ship or hold rule.
         Evidence: AC10 "A headless run that launches a general-purpose agent sends no opus pin" (the reword note says "The headless-run sentence stands as written"). Phase 1 records counts and a NO_TEST stop only. Item 2 gets a decision rule (spec.md:430); AM01 gets none.
         Reading: if the on arm shows VIOLATED runs (opus pins), one coder records the counts and ships the line. Another holds the line, since the AC fails. The plan should say which, and which phase's criterion fails when the on arm pins opus.

GAP      Phase 0 Success Criteria, "Dispatch-verified"  The expected count is wrong: correct code gives 6, not 3.
         Evidence: criterion: "`rg -n -c 'edits_owners_file|file_io_through_tools|agent_model_allowed' rule_meter.py` finds 3 lines". The prescribed code has six lines that match. Each `if detector == "<name>":` line matches, and so does its `return tool_call_detectors.detect_<name>(...)` line, because `detect_edits_owners_file` contains `edits_owners_file` (likewise for the other two). `rg` finds none of the three names in rule_meter.py today.
         Reading: a coder who follows the code block exactly fails the criterion. To get 3, they would have to change the specified code.

GAP      Phase 1 files vs AC16  Phase 1 edits dotfiles files that AC16, read literally, forbids, and the plan records no ruling on the conflict.
         Evidence: AC16: "the only dotfiles edits are `claude/.claude/CLAUDE.md` and `claude/.claude/orchestration.md` on the lane branch". Phase 1 edits `docs/rule-anchors.md`, adds `docs/changes/notes/<date>-<slug>.md` and regenerates `docs/changes/changelog.md`. Phase 2 (in the other extract) edits `opencode/.config/opencode/AGENTS.md`. AC14, AC2 and AC21 require these edits.
         Reading: the Close pass "reconciles every id" and will find AC16 failing as written. The plan should record a reading of AC16 (for example, "only prompt-file edits are these two") with who signed it off and when, in 03-decisions.md, as the global AC rule requires. Without that, Phase 4 has to guess.

NIT      Current State Analysis  The scenario count is stale.
         Evidence: "has 107 scenarios". `python3 -c "...len(json.load(open('rule_meter_scenarios.json')))"` returns 114.

NIT      Phase 0 §4 / Phase 1 "Test-verified"  `-k agent_model` depends on test names the plan never fixes.
         Evidence: Phase 0 asks for "one test per detector" without naming them. Python here is 3.14.10, where `-k` matches `*agent_model*` case-sensitively against the full test id.
         Reading: if the coder puts the tests in a class like `AgentModelAllowedTest` with method names that lack `agent_model`, they are filtered out and the run ends "NO TESTS RAN" (exit 5). Naming the test class or method pattern would close this.

NIT      Phase 1 §5  `--by claude-code/claude-fable-5-1` is hardcoded. That is the actor name of a different model than the coder that will run the step. Use the running coder's own model id.

Claims settled against the tree (each holds unless listed above):
- `rule_meter.py` symbols are where the plan says: :1435 `grade` (an if-chain with no else; an unknown detector falls through and returns None, not a ValueError, but that does not matter here), :1594, :1631, :1696, :2024, :2365, :2427, :355, :274. `parse_stream` starts at :235.
- `HERE` is put on `sys.path` at :57. `rule_meter_checks/` has no `__init__.py`, so the namespace import works. Its only other consumer is `CHECK_SOURCES` (:161), which uses files by name.
- `test_rule_meter.py:192` is `KeepsUserInThisPaneTest`, and :20 has the `bash()` helper. The plant dict test is at :1270.
- `check_splits` needs no family unless a scenario sets `split`.
- `claude/.claude/CLAUDE.md:34` and `orchestration.md:6` (Explore) and `:16` (auto-mode line) quote correctly.
- The `settings.json:460` Agent matcher runs `agent-model-guard.sh`. The other Agent hooks (:256, :301, :424) are handback and telemetry, not model hooks. No other script under `scripts/` gates the model.
- Every file in `agents/` pins a model. `general-purpose.md:4` is `model: sonnet`. There is no web-fetch, Explore or Plan agent file.
- Anchor rows 2ebac3a6, 37b5ea1e and a1ceac7b exist. `rule-anchors.sh check` exits 0 and reads its own tree (`CLAUDE_DIR` from `BASH_SOURCE`). `docs/rule-anchors.md:11-16` is the procedure.
- `opencode/.config/opencode/AGENTS.md:34` carries the go-ahead sentence.
- The `build_changes.py` options (`new --by --root`, `--check`, `--root`) exist, and the findings default is the agent-evals repo. The `rule_trials.py` subcommands (`build`/`search`) exist.
- The referenced finding and change-note files exist.
- Outside the tree (cannot settle here): whether headless `claude -p` records Agent calls as `tool_use` named `Agent` (the plan itself marks this declared-only and adds a stop for it).

VERDICT: NEEDS CHANGES (2 blocker, 4 gap)
