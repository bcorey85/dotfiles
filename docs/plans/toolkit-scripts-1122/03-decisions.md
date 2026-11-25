# Design Decisions — toolkit-scripts-1122

> Research: ./02-research.md
> Status: 15/15 resolved

## Queue

- [x] D1. Item 1: the target gate no longer exists; what the lane does with the item — from backend-architect, ruled by agent-evals-c3
- [x] D2. Item 3: new verb, `log --help` epilog, or split first — from backend-architect
- [x] D3. Item 3: which skill lines move to the script and which stay — from backend-architect
- [x] D4. Item 4: script location and shared lock module — from backend-architect
- [x] D5. Item 4: CLI shape (three subcommands vs one run) — from backend-architect
- [x] D6. Item 4: backup layout (`lib/file_backup` vs `<basename>.bak`) — from backend-architect
- [x] D7. Item 4: what stays as agent prose — from backend-architect
- [x] D8. Item 2: what the guide skill keeps — from backend-architect
- [x] D9. Item 2: test coverage without the binary — from backend-architect
- [x] D10. Rule-meter detector location (architect deviation DV1) — from backend-architect, sent to agent-evals-c3
- [x] D11. Change-file root (DV2) — from backend-architect, sent to agent-evals-c3
- [x] D12. Restore of an old-layout lock (DV3) — from backend-architect
- [x] D13. Step 4 gate-block sentence (DV4) — from backend-architect
- [x] D14. Meter run budget — from backend-architect, ruled by agent-evals-c3
- [x] Q1. Item 2: does `guide --format-version` print the block and field schema, or a version string only — from backend-architect; ruled by agent-evals-c3 2026-11-22: unproven, tables stay (folded into D8)

## Resolved

### 1. Item 1 is dropped, not re-aimed

**Choice**: Do no work on `review-commit-gate-places-a-cd-to-a-literal-repo`. The queue file on origin/bench-base already reads `status: dropped` (commit ed04efba, 2026-11-22 17:11, "drop two stale chores") with the outcome "superseded: dotfiles 4732aaf3 removed review-commit-gate and moved the reviewed-tree check to push time in git-discipline-gate, which already reads the branch of a cd or -C target". No change file, no test.
**Reasoning**: agent-evals-c3 ruled (2026-11-22) that the item is dropped when the gate's behavior already covers the form. The architect's probe of `lib/git_calls.py` shows `cd /abs/repo && git push` placed at `/abs/repo`. The queue state records the drop. The lane recorded the rule-8 facts here so a later reader does not reopen it.
**Alternatives rejected**: (a) a regression test class in `PushReviewedTreeTest` with absolute, `$VAR` and relative cases. Its one informative case, `cd $VAR && git push` from a reviewed clean cwd, fails today and needs a gate change that makes every unplaced push fail closed, including `cd "/quoted/path"` and repos with no record: a behavior change the item never asked for. The relative case contradicts the item's AC: the shared helper follows a relative `cd`, and rule 8 credits it, which is right since git runs there. (b) Un-follow relative `cd` in rule 8: a second notion of placement against the brief's "one shared helper".
**Trade-off accepted**: the credit leak the architect found (an unplaced push judged in the hook's cwd, and `cd /abs/repo && gh pr create` judged in `payload_cwd`) stays unfixed and untested. No session has hit it; the size rule says it gets a queue item, not code, until one does.

### 2. Item 3: split the log-input grammar out, then print the template from `log --help`

**Choice**: Move the log-input grammar of `skills/refactor/scripts/refactor_flow.py` (the `require_*` helpers through `validate_log`, `read_refactor_log`, `read_modifier`, and `RefactorFlowError` or a base it inherits) into a sibling module `refactor_log_input.py` that also owns a `LOG_TEMPLATE` constant, a parseable branch-mode JSON object. `refactor_flow.py` imports them and re-exports `RefactorFlowError`, so `module.RefactorFlowError` in the tests keeps working. The `log` subparser gets `help=` text and an `epilog` built from the constant with `RawDescriptionHelpFormatter`, between two fixed marker lines. The docstring copy at the top of `refactor_flow.py` shrinks to a pointer at `log --help`. No new verb.
**Reasoning**: `refactor_flow.py` is 1097 lines, over the 1000-line no-new-verb rule in `docs/toolkit-script-rules.md`. The split puts the template beside the validator that checks it, the "one grammar" rule. `--help` is the form the queue item asks for ("prints the log template") with no new surface.
**Alternatives rejected**: a `--help` epilog with no split: fits the rule as worded, but leaves the file at 1097 lines and the template apart from its validator, so the two drift. A `template` verb after the split: a bigger surface than `--help` for no gain, and a verb the skill must then name. A JSON data file beside the script, named in each prep `NEXT:` line: a second file to keep in sync, and the item says "prints".
**Trade-off accepted**: about 165 lines move, so the diff is larger than the help text alone, and `ruff.toml` needs an entry for the new skill-folder module as `refactor_flow.py` has.

### 3. Item 3: format lines move, judgment lines stay

**Choice**: `skills/refactor/SKILL.md` Step 5 keeps about three lines: the trigger (when to log), the command (`refactor_flow.py log <path>`), and "the input shape is in `refactor_flow.py log --help`". The key list and the fenced JSON example move to the script. The judgment bullets stay in the skill unchanged: one entry per smell, never escape mechanical-sweep matches or legacy targets, and the `miss_reason` source. `skills/close-branch/SKILL.md` line 68 repoints from "Step 5 of the refactor skill" to `log --help`. The `## Instructions` rule-anchors row for the refactor skill gets a new hash. `test_the_log_input_example_in_the_skill_logs_on_the_first_call` in `tests/scripts/test_refactor_flow.py` becomes: pull the JSON between the marker lines of `log --help`, log it in branch mode, and assert `SKILL.md` has no fenced `json` block.
**Reasoning**: agent-evals-c3 ruled that every cut or reworded rule gets rule-meter arms before commit. A template and a key list are format, owned by the script; the three judgment bullets are rules, and they stay so no meter run is needed. The test's new assertion stops the template from drifting back into the skill.
**Alternatives rejected**: cutting the judgment bullets too: each is a rule and needs meter arms; the item did not ask for it. Keeping the fenced example in the skill as well: two copies, the drift the item exists to end.
**Trade-off accepted**: a reader of the skill has to run `--help` to see the shape.

### 4. Item 4: `tools/mutation_lock.py` on a new `lib/calibration_lock.py`

**Choice**: New script `claude/.claude/scripts/tools/mutation_lock.py`. New module `claude/.claude/scripts/lib/calibration_lock.py` that owns the lock path with its fallback, the field reader, the timestamp form `%Y-%m-%dT%H:%M:%SZ`, `lock_is_live` and the run timeout constant, with its module docstring naming it the owner. `gates/calibration_guard.py` imports those from the module and keeps its own path and its hook contract; `tests/scripts/test_calibration_guard.py` passes unchanged.
**Reasoning**: the lock path and liveness exist once today, inside `calibration_guard.py`. A second copy in the new script breaks the one-owner rule in `scripts/CLAUDE.md`. agent-evals-c3 ruled that a module owner goes in its docstring, not a CLAUDE.md Owners line. `pi/.pi/agent/settings.json` and `settings.json` run `calibration_guard.py` by path, so the gate stays where it is.
**Alternatives rejected**: putting the writer in `calibration_guard.py` itself: a hook gate would take write verbs and the agent would call a gate; also the hook runs on every SessionStart and must stay small. A self-contained script with its own path and liveness code: two owners of the lock format, and the next field change breaks one of them.
**Trade-off accepted**: a refactor of a live hook gate with no behavior change, which the guard tests must prove.

### 5. Item 4: three subcommands

**Choice**: `mutation_lock.py check <target>`, `mutation_lock.py lock <target> --class <name> --line <n> --owner-pid "$PPID"`, `mutation_lock.py restore --owner-pid "$PPID" --run-id <run-id>` (the run id added by D19). `check` runs the preconditions a script can check and lists them in `--help`: the target exists and is a regular file inside the worktree, no live lock at either lock path (a stale lock stops with the UNRESTORED text, backup path and recovery lines), the backup folder is writable. `lock` repeats the checks under `lib/file_lock.hold_exclusive` on a sidecar `.lock` file, saves the backup, and writes `lock.json` with `write_text_atomically`, fields identical to today's prose: `ts`, `kind` `mutation-test`, `writer` `mutation-tester`, `file`, `backup_path`, `pre_hash` (16 hex of sha256), `class`, `line`, `worktree`, `owner_pid` as an int, and `run_id` (D19). `restore` refuses a lock whose `writer`, `owner_pid` or `run_id` differs, a missing backup, or a lock found only at the legacy path; copies the backup back; verifies the hash; on mismatch keeps the lock, prints target and backup paths and exits non-zero; on success removes the lock. Exit codes and output lines are named constants. Each verb ends with a `NEXT:`, `STOP:` or done line.
**Reasoning**: the agent's own Edit and test runs sit between lock and restore, so one `run` verb cannot exist. `check` before the baseline suite run keeps the agent from running a slow baseline against a locked repo. The field names stay so a lock written by the old prose still restores and `calibration_guard.py` reads it unchanged.
**Alternatives rejected**: one `run` verb: impossible, the Edit happens in the agent. Two verbs with `lock` doing the check: the baseline run happens before the lock check, so a locked repo costs a full suite run before the stop. Unlocking a stale lock automatically on `lock`: destroys evidence of an unrestored mutation; the guard's own rule is stop and report.
**Trade-off accepted**: three calls in the agent instead of one script run; `--owner-pid "$PPID"` is passed by hand because a Python child's parent is the Bash tool shell, not Claude.

### 6. Item 4: backup through `lib/file_backup`

**Choice**: `lock` saves the backup with `lib/file_backup.save_files` under `${XDG_STATE_HOME:-$HOME/.local/state}/claude-calibration/backups/`, laid out as `<relpath>` under the worktree, and `restore` uses `restore_changed`. `discard` is never called: it removes the whole backup folder.
**Reasoning**: the helper exists and is the owner of backups; a `shutil.copy2` in the new script is a second copy. `copy2` gives the copy the source's mtime and mode bits, so after a copy back the target carries the backup's old mtime; `restore` then sets the target's mtime to now, so a build tool sees the file as changed.
**Alternatives rejected**: keep `<basename>.bak` with a direct copy: a second backup helper, and two files with one basename in different folders collide.
**Trade-off accepted**: the backup path in the lock changes from `backups/<basename>.bak` to `backups/<relpath>`. `restore` reads `backup_path` from the lock, so an old lock still restores from its own path.

### 7. Item 4: two preconditions stay as agent prose

**Choice**: `agents/mutation-tester.md` Step 0 loses the count in its heading and keeps two bullets a script cannot check: the dispatch names the test command, and the dispatch names the file. The missing-test-command bullet stays a bullet in Step 0, where its rule-anchors row says a measurement placed it. Steps 1 and 4 become one `mutation_lock.py` line each. Step 0 gains the `check` line. The "Never `git checkout` / Write / Edit the target outside the one mutation" lines stay as they are. The `docs/rule-anchors.md` rows at lines 129-137 get new section keys and hashes through `rule-anchors.sh`. The opencode port at `opencode/.config/opencode/agents/mutation-tester.md` gets the same steps, the legacy lock path removed, and "all four" cut.
**Reasoning**: agent-evals-c3 ruled that the precondition list is owned by the script's `--help`, so the heading count goes. Rules cut from the agent need meter arms; the lines that move are commands, not rules, so no cut or reword of a rule happens. The opencode patch is named by the item.
**Alternatives rejected**: cut the "never git checkout" lines as covered by the script: the script does not stop a checkout, and the cut needs meter arms. Leave the opencode port: the item names it, and it still writes the legacy path the guard treats as a fallback.
**Trade-off accepted**: the agent keeps two prose preconditions, so the list lives in two places: the script's `--help` for what it checks, the agent for what only the dispatch can show.

### 8. Item 2: the guide skill keeps the schema tables and one card; the pointer-to-binary cut waits

**Choice**: `skills/guide/SKILL.md` keeps the commands block, the batch keys, the card envelope, the block table, the field table, the "judgment call with evidence" worked card, rules 1, 2 and 6, and the answers shape. The other two worked cards are cut. Rules 3, 4, 5, 7 and 8 get rule-meter on and off arms first: a rule the meter grades as a no-op is cut and its counts go in the change file; a rule the meter cannot grade stays and is listed in the change file's `unmeasured`. New scenarios go in `~/agent-evals/bin/rule_meter_scenarios.json`, detectors in `bin/rule_meter_checks/` with tests, `bin/rule_meter.py` untouched, after `git -C ~/agent-evals status bin/`. The queue outcome and the change file record that the pointer-to-binary cut of the tables waits on a `guide` build that prints the schema.
**Reasoning**: agent-evals-c3 ruled (2026-11-22, Q1): the binary is not installed here, nothing proves `--format-version` prints the schema, and the skill's own JSON uses `guide_version` as a version key, so the tables stay. Earlier ruling: keep one worked card; rules 3-5, 7, 8 cut only after meter arms; ungradeable rules stay.
**Alternatives rejected**: cut the tables and point at `guide --format-version`: if the binary prints only a version string, `/guide` users have no format reference and the skill cannot be followed. Keep all three cards: the item's point is the cut, and the ruling names one. Cut the rules without meter arms: against the standing ruling. A fake `guide` binary in the tests that prints the tables: a second owner of the format.
**Trade-off accepted**: the item's saving shrinks from about 120 lines to the two cards and any rules the meter clears; the table cut is a follow-up once a build prints the schema.

### 9. Item 2: no new test for the guide skill

**Choice**: no new test. Lint, `test_log_escape`'s prompt walk, the dead-prose and stale-prose gates cover the file as text. The guide skill has no rule-anchors rows and no test reads it, so neither list changes.
**Reasoning**: the binary is not installed on this machine, and a test cannot check a format the binary owns without becoming a second owner.
**Alternatives rejected**: a test that asserts the kept card parses as JSONC and that the skill names `guide --format-version`: it pins text, not behavior, and adds a row to `PROMPT_READING_TESTS` for no catch.
**Trade-off accepted**: a wrong edit to the kept card is caught only by a human running `/guide`.

### 10. Rule-meter detectors for the guide rules live in `bin/rule_meter_guide.py`, merged into `rule_meter_verifier.DETECTORS`

**Choice**: New `~/agent-evals/bin/rule_meter_guide.py` holds pure `(result_text) -> (outcome, evidence)` graders for guide rules 3, 4, 5 and 7 and a `DETECTORS` dict; `rule_meter_verifier.py` imports it and merges the dict into its `DETECTORS` table. Tests in `bin/test_rule_meter_guide.py`. `rule_meter.py` is untouched. Rule 8 has no scenario and is listed `unmeasured`.
**Reasoning**: `rule_meter.py` reaches `rule_meter_checks/` only through subprocess calls hard-coded in it (lines 1226, 1275, 1301, 1309), so a check placed there cannot run while `rule_meter.py` stays untouched. `grade()` dispatches through `rule_meter_verifier.DETECTORS`, the one pluggable path. agent-evals-c3 ruled yes on 2026-11-22, and that the lane commits those agent-evals files itself (`bin/` is clean), with `pull_keep_index.py` before the push, as lane-common says for queue files.
**Alternatives rejected**: a hidden check in `rule_meter_checks/`: needs a new subprocess call in `rule_meter.py`, against the ruling. Running the guide binary in the scenario: it is not installed, so the task has the model write `questions.json` and paste the batch as strict JSON in its reply.
**Trade-off accepted**: a third detector module beside `rule_meter_verifier.py`; `rule_meter_verifier.py` gains one import.

### 11. Change files are written to the worktree's `docs/changes`

**Choice**: `build_changes.py new ... --root /home/brandon/dotfiles-toolkit-scripts-nov22/docs/changes`, then `build_changes.py --root <same>`.
**Reasoning**: the lane rule's path `/home/brandon/dotfiles/docs/changes` is the master checkout; a note there is untracked on master and absent from this branch's commit. The script's default is the checkout it runs from. agent-evals-c3 ruled yes on 2026-11-22.
**Alternatives rejected**: the master checkout path: the note never reaches the branch, and the `[change](...)` links in `docs/rule-anchors.md` point at a file the branch lacks.
**Trade-off accepted**: none found.

### 12. `restore` sends an old-layout lock to a fallback stop

**Choice**: a lock whose `backup_path` is not `backups/<file>` under the state folder (the old prose wrote `backups/<basename>.bak`), or that lacks `worktree` or `file`, makes `restore` print the guard's manual `cp` and `rm` lines, keep the lock, and exit 1.
**Reasoning**: `lib/file_backup.restore_changed` expresses only `backups/<relpath>`. Restoring the old layout needs a second copy helper, and no session has hit the case. The size rule in `docs/toolkit-script-rules.md` gives it the fallback stop. This narrows decision 6's "an old lock still restores from its own path": the old lock is reported with its recovery commands, not restored by the script.
**Alternatives rejected**: a `shutil.copy2` branch for the old layout: a second backup helper for a case nobody hit.
**Trade-off accepted**: one manual restore for any lock the old prose left behind at the time this ships.

### 13. The Step 4 gate-block sentence stays, retargeted, and is listed `unmeasured`

**Choice**: "If a safety gate blocks that removal … print the exact command for your caller … Never retry by another mechanism" keeps its rule and its trigger becomes "`restore` ends with any other `STOP:`". The change file lists it under `unmeasured` as a reworded rule that stays.
**Reasoning**: the `rm` it guarded moves into the script, so the trigger text has to change; the rule itself (hand the command to the caller, never retry another way) still binds the agent. No meter scenario can make the script's unlink fail on demand, so the arms cannot be run. The standing ruling says every reworded rule gets arms or goes in `unmeasured`.
**Alternatives rejected**: cut the sentence as covered by the script: the script prints the command, but nothing else stops the agent from retrying by another route. Treat it as a pure command move: the sentence is a rule, not a command.
**Trade-off accepted**: one unmeasured row in the mutation-tester change file.

### 14. Meter budget for guide rules 3, 4, 5 and 7: 24 runs, then up to 24 more

**Choice**: one run per cell first (4 rules × 3 levels × 2 arms = 24 opus runs). A rule whose off arm complies at least as often as its on arm at every level after that pass gets a second run per cell (6 more) to confirm; a rule the on arm clearly wins at any level stays and gets no more runs. Cut a rule only when the confirmed second pass holds the same reading at every level. Rule 8 stays and is listed `unmeasured`. Per-arm counts go in the change file.
**Reasoning**: agent-evals-c3 ruled this budget on 2026-11-22 in place of the architect's 72 runs.
**Alternatives rejected**: three runs per cell up front (72 runs): spends two thirds of the budget on rules the first pass already shows the on arm winning.
**Trade-off accepted**: a cut rests on two runs per cell, so one odd run at one level keeps a rule that a larger sample would have cut.

### 15. `restore` on a lock it does not own prints the recovery line

**Choice**: `STOP_NOT_OURS` (another writer or another owner pid) is followed by `cp <backup> <target> && rm <lock>` with the real paths, each printed as one pasteable shell word (double quotes, or single quotes when the path holds a character double quotes would expand or end on), so the caller can recover by hand when `$PPID` differed between `lock` and `restore`. Narrowed 2026-11-24 (AC18 reword): the recovery line is printed only for a stale lock; a live lock of another run stops with `STOP_LIVE_LOCK` and no commands, so a caller never overwrites a running mutation. The `$PPID` case still gets the line once the old owner pid is dead or the lock has timed out.
**Reasoning**: ruled by agent-evals-c3, 2026-11-22 (damage-path Q1).
**Alternatives rejected**: refuse with the STOP alone and leave recovery to the guard's text: the guard's text is one hop further from the agent that holds the paths.
**Trade-off accepted**: a printed `rm` line that an agent could run against a lock it does not own; the Step 4 gate sentence (D13) still says to hand the command to the caller.

### 16. `check` and `lock` refuse a target with uncommitted edits (reversed by D18)

**Choice**: a sixth precondition, after the backups-folder check: `git status --porcelain -- <relpath>` prints nothing, else `STOP_DIRTY_TARGET` naming the file and printing that status line. Listed in `PRECONDITIONS`, so `--help` shows it.
**Reasoning**: ruled by agent-evals-c3, 2026-11-22 (damage-path Q3): uncommitted edits mean another writer is live, and a mutation on top of them muddles whose bytes `restore` brings back.
**Alternatives rejected**: proceed, the backup holding the edited bytes; warn and proceed. Both leave the bytes' owner unclear.
**Trade-off accepted**: a mutation run cannot start on a dirty file; the caller commits or reverts first.

### 17. A guide rule with fewer than two graded runs at any level stays

**Choice**: such a rule is listed `unmeasured` and kept; the line cut is whatever the card removal and the passing rules give, never a forced count.
**Reasoning**: ruled by agent-evals-c3, 2026-11-22 (damage-path Q2); the ticket's "about 90 lines" is a description, not a criterion.
**Alternatives rejected**: cut to the ticket's line count regardless: that cuts rules the meter never graded.
**Trade-off accepted**: the guide skill stays longer than the ticket estimated when a detector cannot grade a rule.

### 18. `check` and `lock` proceed on a dirty or untracked target and say so

**Choice**: D16 is reversed. `check` and `lock` run on a target with uncommitted or untracked edits; when `git status --porcelain -- <relpath>` prints anything, each prints one `NOTE:` line naming the file and that status line, so the reader knows what `restore` brings back. The lock still refuses a second concurrent run. Step 4's "never `git checkout`" sentence stays. `PRECONDITIONS` holds five entries.
**Reasoning**: reversed by agent-evals-c3, 2026-11-22 (plan review round 1): a test-audit on uncommitted fixes is the case the agent exists for (test-audit/SKILL.md:44 counts the audit's uncommitted fixes), and the byte backup plus the hash-verified restore is the protection; a refusal would also reject every untracked new source file.
**Alternatives rejected**: refuse (D16): breaks the agent's main case and contradicts the kept Step 4 sentence. Refuse only untracked files: same objection for new source files.
**Trade-off accepted**: a mutation can start on a file another writer is editing; the note line and the lock's `pre_hash` are what tell the two apart.

### 19. `restore` needs the run id that `lock` printed (close pass)

**Choice**: `lock` writes a random `run_id` (16 hex) into the lock and ends its `NEXT:` line with `restore --owner-pid "$PPID" --run-id <id>`. `restore` requires `--run-id`; a lock whose `writer`, `owner_pid` or `run_id` differs stops with `STOP_NOT_OURS`, the recovery line printed (stale locks only; a live lock stops with `STOP_LIVE_LOCK`, see the D15 narrowing), target and lock untouched. Both mutation-tester prompts keep the id from the `NEXT:` line, run Step 4 only after `lock` printed `NEXT: apply the mutation`, and their "Any other `STOP:`" bullet reads: report the verdict, state the stop, and print the exact command it names, if any, for your caller to run.
**Reasoning**: every subagent of one session shares `$PPID`, so an owner pid alone let one mutation-tester restore another's lock; and "the target stays mutated" was false for `STOP_NO_LOCK` and `STOP_OLD_LAYOUT`. Found by the close-pass code reviewer. Extends AC14, AC18 and AC23; cuts none. Ruled by the orchestrating session, 2026-11-23.
**Follow-up (gate finding, low, fixed in the same pass)**: a lock with no `run_id` read as `"?"`, so `restore --run-id '?'` passed as ours. `run_id` now reads with an empty fallback and an empty id is never ours; test `test_restore_refuses_a_lock_with_no_run_id_even_for_the_placeholder_id`.

### 20. The guide deliverables are dropped at the rebase onto master (branch end)

**Choice**: `origin/master` deleted the guide skill (`claude/.claude/skills/guide/SKILL.md`, unused since September) and its settings override before this branch rebased onto it. The rebase keeps the skill deleted: the Phase 6 and Phase 8 edits to `SKILL.md`, `tests/scripts/test_guide_skill.py`, its `PROMPT_READING_TESTS` entry in `tests/changed_scope.py` and the guide change note are dropped. The Phase 6 to 8 commits keep only their plan-document edits. The meter scenarios and detectors in `~/agent-evals` (Phase 7, D10) stay: they grade rules in the skill's history and are not toolkit files.
**Reasoning**: a rebase that restored a skill master deleted would undo master's cut. ACs 26, 27 and 28 are cut, not met, and AC1's delivered scope with them. Ruled by agent-evals-c3, 2026-11-23.

### 21. One Step 4 `STOP:` bullet, and the state root from `script_utils.xdg_state_home` (post-rebase review)

**Choice**: the two Step 4 bullets of D13 and D19 ("restored but the lock could not be removed" and "any other `STOP:`") carried the same action word for word, so both mutation-tester prompts keep one bullet: any `STOP:` is reported with the exact command it names, never retried by another mechanism. The mutation-tester change note lists the merged bullet under `unmeasured`. `calibration_lock.state_folder` reads the XDG state root from its owner `script_utils.xdg_state_home()` and `legacy_lock_path` from `pathlib.Path.home()`; the `environ` parameters are gone.
**Reasoning**: the D13 rule still binds; only its trigger text is folded. The toolkit rule gives each fact one owner, and the state root had a second reader. Raised by the post-rebase branch review, 2026-11-23.

### Sign-offs on ticket criteria (criteria owner: `session`)

- ACs 26-28 cut: master deleted the guide skill before the rebase; the cut covers every guide deliverable, and AC1's delivered scope goes with it (D20). Ruled by agent-evals-c3, 2026-11-23.
- AC33 (a human running `/guide` can still follow the trimmed skill) cut, and AC31 (a change note per item) narrowed to the two kept items: both fall under the D20 cut of every guide deliverable: the guide skill is gone from master, so AC33 cannot run, and AC31 covers the two kept notes. Ruled by agent-evals-c3-owner, 2026-11-24.
- AC9 reworded: "same output for plain paths; a path with shell characters comes out as one pasteable shell word", because `calibration_lock.recovery_commands` quotes a `cp`/`rm` path through `shell_word` when it holds `$`, a backtick, `\`, `!`, `"` or a newline. The criteria file holds the reword; the criteria-file wording awaits the user's confirmation. Ruled by agent-evals-c3-owner, 2026-11-24. Reworded again the same day: the closing sentence of the unrestored-lock message no longer names the deleted /calibrate skill ("Do not dispatch mutation-tester until this lock is gone — it refuses to seed on top of an unrestored seed"), so "same output for plain paths" holds apart from that sentence; the guard test pins the new text. Ruled by agent-evals-c3-owner, 2026-11-24; the criteria-file wording of this second reword awaits the user's confirmation (ruled adopt by agent-evals-c3-owner, 2026-11-24).
- AC18 reworded: "`restore` refuses a lock written by another writer, owner pid or run id; a stale one prints the `cp <backup> <target> && rm <lock>` recovery line, each path one pasteable shell word; a live one stops with `STOP_LIVE_LOCK` and no commands", because printing cp/rm for a live run of another agent let the caller overwrite that run's mutation (found by the branch review, 2026-11-24). D15 and spec lines 209 and 380 follow this wording. `tests/scripts/test_mutation_lock.py` pins both the live STOP_LIVE_LOCK path and the stale recovery line. Ruled by agent-evals-c3-owner, 2026-11-24; confirmed by the user on 2026-11-25 13:52 (relayed by agent-evals-c3-owner; the loop's `decide` record is in spec.md's Plan Deviations). The criteria-file edit itself stays with the user.
- Review ask accepted (prompt-wording tests): the mutation-tester prompt tests in `tests/scripts/test_mutation_lock.py` keep only structural checks: every `mutation_lock.py` call parses, `lock` takes no `--run-id` and `restore` carries `--run-id <run-id>` and `--owner-pid`, Step 0 holds one `check` call and two prose preconditions (AC24), Step 4 names `git checkout`, `Write`, `Edit`, a `MISMATCH` and a `STOP:` (AC25). The exact-sentence pins are cut. No acceptance criterion changes. Ruled by agent-evals-c3-owner, 2026-11-24, under the lane-ask rule of 2026-11-22; the review loop's `asks-done` record is left for the user.
- AC1 "points to the binary for the format": narrowed out of this branch; the tables stay (D8), delivered scope is AC26-AC28, the pointer waits on a guide build that prints the schema, owner agent-evals-c3. Ruled by agent-evals-c3, 2026-11-22.
- AC3 "the agent calls it in one line": met by three one-line calls, one per step (`check`, `lock`, `restore`; AC23). Ruled by agent-evals-c3, 2026-11-22.
- Ticket #1 and Ticket #2 (item 1's Done-when): item 1 dropped (D1). Ruled by agent-evals-c3, 2026-11-22; recorded in `spec.md` `## Plan Deviations`.
- Guide change note: written at Phase 6 instead of Phase 9 because the pre-commit hook needs a staged note, and the hook's test rule added `tests/scripts/test_guide_skill.py`. Ruled by the orchestrating session, 2026-11-22.
- Refactor, mutation-tester and guide change notes: all three were created before Phase 9 (the pre-commit hook needs a staged note per commit) instead of by `build_changes.py new` in Phase 9; Phase 9 only filled them, indexed them and linked them from the anchor rows. Ruled by the orchestrating session, 2026-11-22.
- Run id on the lock (D19): AC14 gains a `run_id` field, AC18 gains a run-id refusal, AC23's Step 4 line gains `--run-id`; no criterion is cut or narrowed. Ruled by the orchestrating session, 2026-11-23.
- Anchor rows named in Phase 9 (`458c884f`, `6ca266a8`, `84cdf15f`, `d11ed9bc`) were rehashed by Phases 2 and 5 and were rehashed again by the close pass and the post-rebase review (the current hashes are in `docs/rule-anchors.md`); the refactor row already carried its link from Phase 2, so Phase 9 appended the mutation-tester link to the three mutation-tester rows. No acceptance criterion changes.

## Direction & Constraints

- Orchestrating session: agent-evals-c3. Rulings dated 2026-11-22: no Owners lines in any CLAUDE.md, a module owner goes in its docstring; scripts are edited on this branch in this worktree; every cut or reworded rule gets rule-meter arms before commit, with scenarios in `bin/rule_meter_scenarios.json`, detectors in `bin/rule_meter_checks/` with tests, `bin/rule_meter.py` untouched; item 4's precondition list is owned by the script's `--help`; opencode ports are patched where the item names them; item 2 keeps one worked card.
- Corrected premise, item 1: `gates/review-commit-gate` does not exist. It was deleted in dotfiles `4732aaf3` (2026-11-21). The queue item is dropped on origin/bench-base (ed04efba).
- Corrected premise, item 2: the guide skill is `user-invocable-only` in `settings.json:195`, so it is not always-read; the cut saves tokens only on `/guide` turns.
- Corrected premise, item 4: there are four checkable preconditions plus the baseline run. No `/calibrate` skill exists; mutation-tester is the only writer of the lock, and `calibration_guard.py`'s `writer == "calibrate"` branch has no live writer (left alone; out of scope).
- Lock facts the script must keep: `ts` is exactly `%Y-%m-%dT%H:%M:%SZ` UTC, or the guard reads the lock as stale at once; `owner_pid` is compared as a string of an int; a relative `file` joins to `worktree`; `pre_hash` is 16 hex characters of the sha256; the guard falls back to `~/.claude/calibration-lock.json`.
- `tests/parallel_tests.py` `HEAVY_FIRST` keeps `test_refactor_flow.py`; `tests/changed_scope.py` `PROMPT_READING_TESTS` keeps it too (its close-branch read). Any new test that reads `mutation-tester.md` goes in that list, checked by `test_prompt_reader_list.py`.
- Every toolkit edit under `claude/.claude/` gets a change file through `~/agent-evals/bin/build_changes.py new "<title>" --by claude-code/<model id> --root /home/brandon/dotfiles/docs/changes`, then `build_changes.py`. Item 1 gets none (no toolkit behavior changes).
- Suite runs as `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh` after `free -g` shows 8 GB or more available.
- Candidate follow-up queue items, not this lane: `check_push_reviewed` ignores `placed`, so an unplaced push is judged in the hook's cwd and `cd /abs/repo && gh pr create` is judged in `payload_cwd`; `refactor_flow.py` `locked_state_file` and `code/coder_gate.py` call `fcntl.flock` directly instead of `lib/file_lock`.
