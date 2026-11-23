# Plan review, round 1, shard B (plan-reviewer, 2026-11-22)

DUCK     Phase 2: adds the go-ahead exception sentence to `claude/.claude/CLAUDE.md:34` and to the opencode port `AGENTS.md:34`. Plants a scripts Owners CLAUDE.md and `review/pass_credit.py` in the bench. Adds scenario GA01 (opus, rule_source CLAUDE.md, rooted at this worktree), fills the tree-based `edits_owners_file` detector, runs one meter run per cell, writes a `user-rule` change file and rehashes row a1ceac7b.
DUCK     Phase 3: adds scenario AB01, which puts the auto-mode notice's words in the task. Fills a regex detector that counts Bash writes and inline interpreters, runs a smoke pass and then 8 neutral runs per arm, and decides off<=on -> delete (line, row 37b5ea1e rehash, AB01 removed, trial note), else keep. It also removes scenario A after a `rule_trials.py build`.
DUCK     Phase 4: runs /close-branch reviewers, one fix coder, a fix-diff gate, the suite under the memory cap and the anchors check, and makes the agent-evals commit with final roots.

Claims checked (command -> result):
- `claude/.claude/CLAUDE.md:34` ends "...or a step a hook denied.": `sed -n 30,36p` -> holds.
- `opencode/.config/opencode/AGENTS.md:34` is byte-identical to that line: `sed -n 30,36p` -> holds.
- `orchestration.md:16` is the auto-mode line, inside `### Tools`: holds.
- Anchor rows a1ceac7b (CLAUDE.md `## Messages to Other Sessions`) and 37b5ea1e (orchestration `### Tools`) exist, and `rule-anchors.sh check` exits 0 today: holds.
- `rule_meter.py` line numbers all hold: `grade` :1435, `collect_file_change` :1214, `WORKTREE_COMMAND` :351, `rule_source_for_arm` :1594, `check_rule_texts` :1631, `write_arm_claude_md` :1696, `plant_files` :2024, `PLANTS` :2365, `claude_command` :2427. `run-all` has `--rule`, `--runs` and `--dry-run`. `build_tree` takes `base_sha` after the plant (:2411-2413), so a diff from `base_sha` sees the lane's edit.
- `test_rule_meter.py:1270` is the exact planted-dict test: holds.
- `build_changes.py` has `new --by --root` and `--check --root`: holds.
- Bench `backend/src/shared/pagination.ts` has `pageResult`/`totalPages`: holds. Bench has no `.claude` folder: holds.
- `rule_trial_notes.json`, `tests/scripts/test_rule_anchors.py`, `tests/parallel_tests.py`, the findings template and the change-note template all exist.
- `bin/test_rule_meter_checks.py` and `tool_call_detectors.py` are absent. Phase 0 (in the other shard) creates both.
- "rule_meter_scenarios.json has 107 scenarios": the tree contradicts it, it has 114.

BLOCKER  Phase 3 "Scenario-A-removed" (and the External Contracts line saying scenario A is the one stale scenario)  `run-all --dry-run` cannot exit 0 after A is removed
         Evidence: `rule_meter.py run-all --dry-run` today dies on A ("rule text not found in /home/brandon/.claude/CLAUDE.md ... 'The git index is the user's'"). I then ran `check_rule_texts` on every scenario except A, one at a time: 27 more fail. B, D, E and F have rule text gone from the live global. L, M, N, O, P, Q, T, U, V, W, W2, W3, X, Y, Z, WT01, CD01, CS01, RF01, RF03, RF05 and PV01 point at toolkit roots that no longer exist. NC01's rule text is gone.
         Reading: `check_rule_texts` (:1631) exits on the first bad scenario. Removing A only moves the failure to B. The plan says "No re-rooting of other scenarios' stale `toolkit_root` values", so a coder following it can never make this criterion pass. D8's merge-order reasoning and AC8's premise ("whose rule text was already gone") treat A as the only case.
         Enumerated: python3 loop calling rule_meter.check_rule_texts({k:v}) for each scenario except A -> 27 failures

GAP      Phase 2 §3, line 190: "`rule_text` starts with the space before 'An' so `remove_once` leaves today's line exactly". This is false
         Evidence: `remove_once` (remove_once.py:15) removes the fragment plus `\s*` after it. The sentence ends the paragraph, so the off arm loses the blank lines too. I ran the simulation in python3: off == today's file -> False, and the text reads `'hook denied.## Compact instructions\n\nWhe'`.
         Reading: the off arm is not "today's line exactly" (D2). The next heading gets glued onto the go-ahead paragraph, in every off-arm run and again in the global-form scenario at the final commit. The arms then differ by more than the one sentence. The plan needs a fragment or placement that `remove_once` can cut cleanly, or it must accept and record the glued off arm.

GAP      Phase 2 GA01 scenario: the bench never meets the go-ahead rule's precondition
         Evidence: CLAUDE.md:34 reads "When the repo's CLAUDE.md names an orchestrating session, a worker acts on that session's go-ahead...". The bench's CLAUDE.md (`~/dev/evals/rulemeter1/base/CLAUDE.md`) names no orchestrating session. Neither the plant nor the task adds one to a repo CLAUDE.md, and the session is named only in the task text.
         Reading: in both arms the rule the sentence attaches to is conditional on something absent from the bench. The task also arrives as the user turn of `claude -p`. A model has no user to "ask instead", so both arms likely just edit the file. That gives counts that satisfy AC2 but say nothing about AC3. One coder will plant a line naming agent-evals-c3 in the bench or the plant; another will run the scenario as written.

GAP      Phase 2 "Test-verified" cannot pass when Phase 2 runs
         Evidence: Phase 2 runs `python3 -m unittest discover -s /home/brandon/agent-evals/bin -p test_rule_meter_checks.py` with no filter. Phase 0 (spec.md:188,194) says each detector's test fails on NotImplementedError until its phase fills the body. `detect_file_io_through_tools` is filled only in Phase 3.
         Reading: the command as written fails at Phase 2 because of AB01's test. Phase 1 used `-k agent_model`. Phase 2 needs a `-k owners` filter, or the coder will guess one.

GAP      Phase 3 §3: the decision rule omits walk ruling W3, now in acceptance-criteria.md AC6
         Evidence: AC6 now says "an errored or NO_TEST cell is re-run once within the budget, then the line is kept if still inconclusive". Phase 3 says only "off ≤ on → delete; on < off → keep".
         Reading: if a cell errors or reads NO_TEST, a coder following the plan sums whatever ran and may delete the line on missing data. AC6 says re-run once, then keep. W2 (equal counts delete) matches the plan.

GAP      Phase 2 and Phase 3 edit files that AC16 forbids
         Evidence: AC16 says "the only dotfiles edits are `claude/.claude/CLAUDE.md` and `claude/.claude/orchestration.md`". Phase 2 also edits `opencode/.config/opencode/AGENTS.md`, `docs/rule-anchors.md` and `docs/changes/notes/*`, and Phase 3 edits `docs/rule-anchors.md` and change notes. AC14 and AC21 require some of these edits.
         Reading: the close pass's AC reconciliation will flag AC16 as failing. The criteria contradict each other (AC16 against AC14 and AC21). The plan should send this to agent-evals-c3 for a ruling and record it in the decision log. It should not route around it silently.

GAP      Phases 2, 3 and 4: no step puts `~/agent-evals` on branch `toolkit-rules-nov22`
         Evidence: `git -C ~/agent-evals branch --show-current` -> `bench-base`. That checkout holds another session's uncommitted `QUEUE.md`, `queue/index.md` and a new queue file. `grep -n 'switch\|checkout\|worktree add' spec.md` finds no step that creates or switches to the branch. Every run command hardcodes `~/agent-evals/bin/...`.
         Reading: one coder switches the shared checkout to a new branch, which moves the other session's uncommitted work with it. Another edits on bench-base and branches only at the final commit. A third uses a worktree, which breaks the hardcoded `~/agent-evals/bin` run paths. The Phase 1 and 3 findings files go to `~/agent-evals/findings/`, which has the same ambiguity.

GAP      Phase 3 §4b (keep branch): the change file has no `kind`
         Evidence: §4a says `kind` `structured` with its finding stem. §4b gives only `change_type` changed and Result. Q4 says items 2 and 3 are both `structured`.
         Reading: `build_changes.py` needs a kind, and a `structured` kind needs a proof stem at runs_per_arm ≥ 8. The guess is probably structured plus the Phase 3 finding, but the plan doesn't say so.

NIT      Current State Analysis: "has 107 scenarios". The file has 114 (`python3 -c "...len(json.load(...))"` -> 114).

NIT      Phase 4 "Scope box": `test -n "$(git diff --name-only dfb9fd4ef..HEAD)"` passes as soon as any commit exists, so it cannot fail on wrong scope. It checks that something changed, not the scope.

NIT      Phase 2 "Rest-unchanged" already passes before the phase runs. It works as a regression guard only, which is fine, but it does not check that the sentence was appended.

VERDICT: NEEDS CHANGES (1 blocker, 7 gap)
