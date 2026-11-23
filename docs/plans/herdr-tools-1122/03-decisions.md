# Design Decisions — herdr-tools-1122

> Research: ./02-research.md
> Status: 20/20 resolved

## Queue

- [x] D1. Where the lane file lives and its format (one reader for resume and status) — from backend-architect
- [x] D2. herdr-lane-resume: new script or a herdr-worktree verb; resume without a second fork — from backend-architect
- [x] D3. When the lane's session id is recorded and refreshed — from backend-architect
- [x] D4. lane-status liveness discriminator and exit code polarity — from backend-architect
- [x] D5. How herdr-phase-change resolves a ListAgents name or a worktree path to a pane id — from backend-architect
- [x] D6. How herdr-phase-change names the report-to session in a slash prompt — from backend-architect
- [x] D7. Which existing step runs the prune — from backend-architect
- [x] D8. pull_keep_index in a shared tree (item 8 AC1) — from backend-architect
- [x] D9. Named ref for the save commit (item 8 AC2) — from backend-architect
- [x] D10. Put-back when both sides changed built pages — from backend-architect
- [x] D11. Review pane label: rename at start; restore on exit? — from backend-architect
- [x] Q1. Lane file placement vs the AC's "beside the worktree" wording — from backend-architect
- [x] Q2. Domain terms "lane", "lane file", "lane list" — from backend-architect
- [x] Q3. Do non-fork herdr-worktree runs create a lane entry — from backend-architect
- [x] Q4. Resume prompt after a /clear phase change: brief or short "go on" — from backend-architect
- [x] Q5. Prune wiring: merge-line rule text vs background run at lane start; post-run count AC wording — from backend-architect
- [x] Q6. Quota line: df per the AC, or scratch-root usage against a cap — from backend-architect
- [x] Q7. Report-to marker: edit slash skills' argument rules — from backend-architect
- [x] Q8. Shared-tree pull: refuse on a diverged branch, or succeed without touching the tree — from backend-architect
- [x] Q9. Should hunk-review-pane clear the review label on exit — from backend-architect

## Resolved

### D2. herdr-lane-resume is a new script; resume never forks again

**Choice**: New `scripts/.local/bin/herdr-lane-resume <name>` with `--close <name>`. It reopens the workspace (`herdr worktree open --cwd <main> --path <worktree> --label <name> --focus`; tuios: `herdr-api workspace create`), then calls `herdr-dev` in a new resume mode that types `claude --resume <session id> --name <name>` with the brief as the start prompt and no `--fork-session`. `herdr-worktree-watch`'s recovery text names `herdr-lane-resume <name>` in place of its hand-built two steps.
**Reasoning**: Lane session (2026-11-22). herdr-worktree is 280 lines of branch-making flow; resume shares only the herdr-dev call. The AC names the command `herdr-lane-resume <name>`.
**Alternatives rejected**: `herdr-worktree --resume <name>` tangles the argument parser with a flow that has no branch, base or push, so a typo in the resume flags would start making a worktree. `herdr agent start --kind claude -- --resume <id>` loses the code/review/console layout and needs a herdr-legal agent name that cannot hold the lane name.
**Trade-off accepted**: herdr-dev grows a second mode and its tests grow with it.

### D3. The watcher and herdr-phase-change write the session id

**Choice**: herdr-worktree writes the lane entry at lane start with an empty `session_id`. herdr-worktree-watch calls the lane CLI's `set-session <name> <id>` as soon as it reads the fork's own id. herdr-phase-change calls the same verb with the post-`/clear` id for the lane whose worktree holds the target agent's cwd. The brief field is replaced by the phase prompt at the same time (see Q4).
**Reasoning**: Lane session (2026-11-22). The fork id exists only after the claude process reports it, which only the watcher waits for; every `/clear` rotates it and only phase-change sees the new one.
**Alternatives rejected**: Picking the newest transcript under `~/.claude/projects/<encoded worktree>/` at resume time guesses; with a reviewer or a second session in the same tree it resumes the wrong conversation.
**Trade-off accepted**: A lane that was `/clear`ed by hand, not through herdr-phase-change, resumes its pre-clear session.

### D4. lane-status matches a lane's agent by cwd and exits 1 when it prints

**Choice**: For each lane entry, lane-status finds the herdr agent whose `cwd` is inside the lane's worktree (the same read as `herdr-worktree-prune`'s agent check). No agent prints `<name>: no agent`; an agent whose `agent_status` is not `working` prints `<name>: <status>`. Memory below `LANE_STATUS_MIN_MEMORY_GB` (default 8) and scratch volume below `LANE_STATUS_MIN_SCRATCH_GB` (default 1) print one line each. Exit 0 when nothing printed, 1 when something did, 2 on a bad lane file or missing tool.
**Reasoning**: Lane session (2026-11-22). Pane ids and session ids both change (reopen, `/clear`); cwd is the one stable key, and prune already uses it. A Monitor until-loop needs an exit code it can test.
**Alternatives rejected**: Matching by stored pane id reports every lane as gone after a workspace reopen. Omitting a lane with no agent hides exactly the dead lane the item exists to surface.
**Trade-off accepted**: Two claude agents in one worktree both print.

### D5. herdr-phase-change resolves names and paths through a Python resolver that imports session_registry

**Choice**: A new `claude/.claude/scripts/tools/session_pane.py resolve <arg>` prints JSON `{"pane_id": ...}` or exits 1 with a reason. A ListAgents name resolves through a new `session_registry.row_for_name(name)` to its `sessionId`, then to the `herdr-api agent list` entry whose `agent_session.value` matches. A path resolves to the one claude agent whose `cwd` is inside its realpath; several print their pane ids and exit 1. Anything else passes to `herdr-api agent get` as today. herdr-phase-change calls the resolver before `agent_field`.
**Reasoning**: Lane session (2026-11-22). `lib/session_registry.py` owns session folders and live rows (scripts/CLAUDE.md); a second reader in jq would copy the `CLAUDE_CONFIG_DIR` override and the pid-liveness check. `scripts/.local/bin/claude-bg` already calls into `~/.claude/scripts`.
**Alternatives rejected**: jq over `~/.claude/sessions` in bash breaks the owner rule and misses the config-dir override, so a session under `CLAUDE_CONFIG_DIR` is never found. Rewriting herdr-phase-change in Python throws away a tested script and its stub harness for one lookup.
**Trade-off accepted**: A bash bin script now depends on the stowed `claude` package being present.

### D8. A pull in a shared tree never sets another session's edits aside

**Choice**: Before setting aside, `pull_keep_index.py` calls `session_registry.other_live_session_in(repo, CLAUDE_CODE_SESSION_ID)`; a missing env var counts as shared. Shared and clean: pull as today. Shared and dirty: when HEAD is not ahead of upstream, run `git merge --ff-only @{u}`; git refuses on an overlapping dirty path and leaves the tree whole, and the script exits 1 naming those paths and the way out. Shared, dirty and diverged: refuse, naming the dirty files and the way out (commit, or wait for the other session, then rerun). Solo path unchanged. A `file_lock` in the git common dir serialises two runs.
**Reasoning**: Lane session (2026-11-22). No store says which session owns which dirty file, so "set aside only this session's files" cannot be known. The AC allows "refuses and names the files and the way out".
**Alternatives rejected**: Setting aside only staged files still removes a coder's unstaged edits from the tree mid-test. Always refusing when shared blocks every push line in the main checkout whenever a second session sits there. A scratch-worktree rebase plus `reset --keep` runs hooks in the wrong tree and doubles the code for a case the AC lets us refuse.
**Trade-off accepted**: In a shared, dirty, diverged checkout the pull is refused and the user commits or waits.

### D9. The save commit gets a ref the moment it exists

**Choice**: Right after `git stash create`, `git update-ref refs/pull-keep-index/<UTC stamp> <saved>`. Every message that names the saved commit also names the ref. `--put-back` accepts the ref or the hash. A successful put-back deletes the ref.
**Reasoning**: Lane session (2026-11-22). AC2 says a failed put-back never leaves the edits only in an unreferenced commit. A ref written only on failure misses a crash between set-aside and put-back.
**Alternatives rejected**: `git stash push`/`stash store` write the shared stash stack other sessions and worktrees pop, which the docstring and the environment forbid. Ref only on failure leaves a kill -9 mid-pull with a dangling commit.
**Trade-off accepted**: An interrupted run leaves a ref under `refs/pull-keep-index/` until the next successful run of the same repo cleans refs older than its own.

### D10. Put-back with clashing built pages uses the hand repair, driver included

**Choice**: When the staged clash set contains any built page and `merge.built-page.driver` is configured, replace the stash-apply fallback with: (1) staged diff `saved^1..saved^2` minus the pages, `git apply --index --3way`; (2) unstaged diff `saved^2..saved` minus the pages, `git apply --3way`; (3) for each page write `saved^1:page`, `HEAD:page`, `saved:page` to temp files and run the configured driver command (substituting `%O %A %B %P`) with cwd at the repo root and `BUILT_PAGE_STASH=<saved>`, then copy `%A` over the page; (4) `git add` the pages. One function serves the main path and `--put-back`. Any step failing exits 1 with the ref and the way out.
**Reasoning**: Lane session (2026-11-22). The hand repair that worked in the incident is these steps. The driver's docstring says it handles a `git stash apply` whose commit `BUILT_PAGE_STASH` names, with base = the stash's parent, so the three files match the commits it checks. Evidence class: declared-only from the docstring; the plan adds a step that runs the real driver once against a dotfiles clone before the branch closes.
**Alternatives rejected**: Hard-coding `build_changes.py` ties a generic tool to one repo's builder and breaks for `~/agent-evals` pages. Widening the no-index route to allow non-page clashes loses the staged/unstaged split for those files, which is the incident's failure.
**Trade-off accepted**: The test needs a stub driver registered in a temp repo; the real driver is exercised by hand once.

### D11. hunk-review-pane renames its pane and leaves the label on exit

**Choice**: When `HERDR_PANE_ID` is set, `herdr-api pane rename "$HERDR_PANE_ID" review` runs at start; a failed rename warns and continues. The EXIT trap does not touch the label.
**Reasoning**: Lane session (2026-11-22). The AC asks for the rename. herdr-dev's review pane carries the label by design and would lose it after a plain hunk quit.
**Alternatives rejected**: Clearing the label on exit makes herdr-dev's review pane unfindable after the user quits hunk once.
**Trade-off accepted**: A hand-started pane that dropped back to a shell still carries `review`, and a jump to it fails on the missing state dir as today.

### Q3. Only `--fork` creates a lane entry

**Choice**: herdr-worktree writes a lane entry only on `--fork`.
**Reasoning**: Lane session (2026-11-22). A lane is a forked worker with a brief and a session to report to. A popup-made worktree has neither.
**Alternatives rejected**: Writing an entry for every worktree gives lane-status rows with no session to resume and no agent, so every popup worktree reads as a dead lane.
**Trade-off accepted**: None.

### Q4. The lane file holds the latest prompt, and resume sends that

**Choice**: herdr-phase-change replaces the entry's `brief` with the phase prompt when it records the new session id. `herdr-lane-resume` sends whatever `brief` holds.
**Reasoning**: Lane session (2026-11-22). The AC says resume "sends the brief from that file". After a phase change the original brief is stale and would re-run eng-spec in a session that is on /code.
**Alternatives rejected**: Always sending the original brief restarts the wrong phase. A fixed "go on" prompt gives a resumed pre-phase-change session no brief at all.
**Trade-off accepted**: The original brief is lost from the entry after the first phase change; the git log and the plan carry it.

### Q6. lane-status prints both a df line and a scratch-usage line

**Choice**: `df -P` on the scratch root (`hook_input.claude_code_temp_root()`) below `LANE_STATUS_MIN_SCRATCH_GB` prints a line, as the AC words it. A second check sums the scratch root's usage (`du -sk`) against `LANE_STATUS_SCRATCH_CAP_GB` (default 4) and prints a line when over, because the tmpfs `usrquota` that ran out is invisible to df.
**Reasoning**: Lane session (2026-11-22). The AC names df; the incident needs the usage line.
**Alternatives rejected**: df alone misses the row-6044 failure. Usage alone fails the AC's test shape.
**Trade-off accepted**: A `du` over the scratch root on every poll.

### Q8. Diverged and dirty in a shared tree: refuse

**Choice**: As D8: refuse with the dirty files and the way out.
**Reasoning**: Lane session (2026-11-22). The AC permits refusal.
**Alternatives rejected**: A scratch-worktree rebase doubles the code and runs hooks in the wrong tree.
**Trade-off accepted**: The user commits or waits before pushing from a shared, diverged checkout.

### Q9. No label clearing on exit

**Choice**: See D11.
**Reasoning**: Lane session (2026-11-22).
**Alternatives rejected**: See D11.
**Trade-off accepted**: See D11.

### D1 / Q1. Lane file: one JSON per lane under `~/.local/state/herdr-lanes/`

**Choice**: `${XDG_STATE_HOME:-$HOME/.local/state}/herdr-lanes/<name>.json`, one object per lane: `name`, `worktree`, `main_checkout`, `branch`, `brief`, `session_id`, `reports_to`, `started_at`. One Python owner, `claude/.claude/scripts/lib/lane_entries.py`, reads and writes the format; a CLI `claude/.claude/scripts/tools/lane_entries.py` (`add`, `set-session`, `set-brief`, `remove`, `get`, `list`, `check`) is the only way bash scripts touch it. Writes go through `write_text_atomically`. A file the grammar does not parse stops with the file, the field and the expected form.
**Reasoning**: agent-evals-c3, 2026-11-22: the state folder meets the AC; durability and a cross-repo list were the intent.
**Alternatives rejected**: A per-worktree git dir file dies with `git worktree remove` and nothing knows which repos to scan, so lane-status cannot list lanes across agent-evals and dotfiles. A sibling file in `~/dev` clutters the folder and is listed by nothing. The scratchpad or `/tmp` is wiped by the reboot that caused the incident.
**Trade-off accepted**: The entry is not literally beside the worktree; a removed worktree leaves its entry until `--close` runs.

### D6 / Q7. Report-to marker appended to the slash prompt; no skill edit

**Choice**: herdr-phase-change resolves the sending session's ListAgents name (`CLAUDE_CODE_SESSION_ID`, else `pane current` → `agent_session.value`, through `session_registry.session_display_name`) and appends ` [report to session <name>]` to the prompt; a slash prompt included. No name resolvable: exit 1, sent nothing, as the pane case does today. No skill file changes in this lane.
**Reasoning**: agent-evals-c3, 2026-11-22: the code-skill lane owns SKILL.md this round. If a run treats the marker as a run note, report it to agent-evals-c3, who hands it to the code-skill lane.
**Alternatives rejected**: A second plain prompt after the slash one lands mid-run or waits for the whole phase, so the worker reports nowhere until then. Editing `/code`'s argument rule is another lane's file.
**Trade-off accepted**: `/code <plan> [report to session X]` passes the marker to coders as a run note until the code-skill lane strips it.

### D7 / Q5. `herdr-lane-resume --close` runs the prune; no orchestration.md line

**Choice**: `herdr-lane-resume --close <name>` removes the lane entry, then runs `herdr-worktree-prune --apply` in the lane's main checkout. `herdr-worktree-prune` gains a keep, `check_lane_open`, for a worktree that has an open lane entry (read through the lane CLI's `list`). The orchestrating session calls `--close` after the merge lands. The count AC reads "no worktree whose lane is closed, merged and clean": current, locked, stashed, held and squash-merged trees stay, and the criteria file says so.
**Reasoning**: agent-evals-c3, 2026-11-22. No merge-line generator exists; wiring the prune into close pairs the two on one user action and needs no rule text and no new hook process.
**Alternatives rejected**: A SessionStart hook run would prune in every repo a session starts in, the work machine included, and is banned as a new hook process. A detached prune at lane start removes at the next lane start, not at merge, so the 231 trees wait for the next fork. An orchestration.md line needs a CLAUDE.md-class edit this lane cannot make and depends on a model writing the line.
**Trade-off accepted**: The user waits on the first `--close` while the prune re-checks 231 trees (lsof plus two herdr lists each); a lane merged without `--close` stays until the next close.

### Q2. Terms

**Choice**: "lane", "lane file", "lane list" as the ACs name them. No glossary entry.
**Reasoning**: agent-evals-c3, 2026-11-22.
**Alternatives rejected**: "worker" (glossary open question 2) is not the word the ACs use; renaming now would make the ACs and the scripts disagree.
**Trade-off accepted**: `lane` stays overloaded with the review run's `--lane` option.

### P1. Architect plan deviations (2026-11-22)

**Choice**: Six deviations the backend-architect raised against D1, D9 and D10 are accepted by the lane session and recorded here; the spec carries the accepted form.
1. The lane CLI is `tools/lanes.py`, not `tools/lane_entries.py`: a `tools/lane_entries.py` would shadow `lib/lane_entries.py` on `sys.path`.
2. One `set-session <name> <id> [--brief-stdin]` verb replaces separate `set-session` and `set-brief`: one atomic write per change.
3. D9's "the next successful run cleans older refs" is dropped. Older refs are listed in one stderr line and never deleted; a run deletes only its own ref after its own put-back succeeds. An older ref can be the only reference to edits that never went back.
4. D10 step 2 records the index with `git write-tree` after the staged apply and restores it with `git read-tree` after the unstaged `apply --3way`, which stages what it applies (verified in a scratch repo).
5. Change files use `--root /home/brandon/dotfiles-herdr-tools-nov22/docs/changes` (this worktree), not the main checkout: the build tool's default is the checkout at the cwd, this branch already carries `docs/changes/`, and the brief forbids work in `~/dotfiles`. Reported to agent-evals-c3 at the phase end.
6. The driver string runs the way git runs it: `%O %A %B %P` substituted with quoted temp paths, through `sh -c`, cwd at the repo root.
**Reasoning**: Lane session (2026-11-22). Each one keeps or strengthens an AC; none cuts one.
**Alternatives rejected**: The ledger's original wording for each, with the failure the architect named.
**Trade-off accepted**: Interrupted runs accumulate refs under `refs/pull-keep-index/` until the user deletes them by hand.


### P2. Criteria walk rulings (agent-evals-c3, 2026-11-22)

**Choice**: Criteria owner is `session`; agent-evals-c3 ruled, quoted: "1 yes. 2 yes. 3 yes. 4 warn and continue, with the warning on stderr naming the path and the error, so the fork still starts. 5 send nothing and exit 1 with a line naming why the sender could not be named. 6 yes, remove the entry and say the folder was already gone. The --root deviation on this worktree's docs/changes stands."
1. AC1 "beside the worktree" is met by the state-dir lane file (D1).
2. AC8 "the lane merge line, or session start" is met by `herdr-lane-resume --close` running the prune (D7).
3. AC9 count reads "no worktree whose lane is closed, merged and clean"; current, locked, stashed, held and squash-merged trees stay (D7).
4. A failed lane-file write at fork start warns on stderr with the path and the error; the fork still starts.
5. herdr-phase-change with no nameable sender sends nothing and exits 1 with a line naming why.
6. `--close` on a lane whose worktree folder is gone removes the entry and says the folder was already gone.
**Reasoning**: agent-evals-c3, 2026-11-22, in reply to the lane session's walk.
**Alternatives rejected**: abort the fork on a failed write; send the prompt without the marker; keep the entry until the folder is checked.
**Trade-off accepted**: a lane started with a failed write is not resumable by `herdr-lane-resume`; the warning is the only record.

### P3. Plan review round 1 rulings (lane session, 2026-11-22)

**Choice**: six rulings on the round-1 BLOCKER and GAP findings, applied to spec.md.
1. `herdr-lane-resume --close` closes the lane's herdr workspace before it removes the entry and prunes: exit 1 while a claude agent inside the worktree is `working`; `herdr workspace close <id>` for each workspace whose `worktree.checkout_path` is the worktree (under tuios, `herdr-api workspace close` matched by `label == name`, since the shim's list was not checked); a failed close stops with the entry kept. Without this the prune's herdr keep holds the tree and AC9 fails.
2. The detached watcher sees that close while the entry still exists and writes `1. herdr-lane-resume <name>` plus one notification. Accepted as noise; the other order (remove the entry first) would lose the lane from the list when the close fails.
3. The Phase 11 ban grep bans only `put_back_without_index`, with `--hidden` (rg skips `scripts/.local/bin` without it), over `claude opencode scripts docs/changes/*.md`. `herdr-worktree-watch.log` and the `herdr-dev <worktree> <ws>` fallback steps stay live. `docs/plans/` and `docs/changes/notes/` are never searched or edited.
4. `session_pane.py sender` prints JSON on every exit (`{"name": null, "reason": "<why>"}` on failure) so bash callers under `set -e` read the reason without parsing stderr.
5. The pull_keep_index lock timeout is `PULL_KEEP_INDEX_LOCK_SECONDS` (default 300), read once; `--put-back` runs under the same lock; the test holder is a Python child on `lib/file_lock`.
6. `--put-back <hash>` makes or finds a ref under `refs/pull-keep-index/` before the apply, so a failed put-back always leaves a named ref; success deletes only that ref.
**Reasoning**: lane session, 2026-11-22, on the architect's revised text for the round-1 reports (`review-round1-shard-a.md`, `review-round1-shard-b.md`).
**Alternatives rejected**: tell the user to close the workspace by hand; widen the ban roots and rewrite old plans; a fixed 300 s lock wait in tests.
**Trade-off accepted**: a hand-made tuios workspace with the lane's label is closed too; one stale log line and notification per deliberate close.

### P4. Plan review round 2 repairs, unreviewed (lane session, 2026-11-22)

**Choice**: round 2 was the last review round (eng-spec step 20), so its 2 BLOCKER and 6 GAP findings go to the orchestrating session as-is; the lane session also wrote the repairs into spec.md so the plan is runnable, and the orchestrating session rules whether a third round reads them.
1. Phase 4 §1: steps 1 and 3 skip `git apply` when the diff is empty (git 2.34 has no `--allow-empty`; `git apply` exits 128 on empty input).
2. Phase 4 §2: the line-159 test is the step-1 conflict test (not renamed to success); line 179 becomes the step-3 conflict test; line 199 asserts the step-5 driver failure; lines 795 and 816 (mocks of the deleted function) are deleted; one empty-diff success case added.
3. Phase 1 §3: the watcher runs `set-session` only when the lane entry exists and logs only its failure, so no-entry tests keep their exact log text; `label` moves above the session-id read; Phase 1 §4 guards an empty `cwd`.
4. Phase 0: the lane lock is `lanes.lock` in both §1 and §4; the fixed 10 s timeout is stated.
5. Phase 3 §2: the failed put-back fixture is a `reference-transaction` hook (Phase 5's shape), not the mock at test line 804.
6. Phase 7 §2: the no-sender stub branches on `$1` (`resolve` succeeds, `sender` fails), since Phase 6's resolve runs first.
7. Manual checks in Phases 6, 7, 9 and 10 run the worktree copies by absolute path with `HERDR_LANES_CLI` and `HERDR_SESSION_PANE`; the Phase 1 probe lane in `S/clone` stays open through Phase 8 and Phase 10 closes it with `--close` against the real prune, asserting the worktree count falls by one.
8. NITs: Phase 12 counts 13 test files; the Phase 4 change file never names the removed function; the shared route fetches into a named ref instead of reading `FETCH_HEAD`; Phase 6/7 test rows have live pids and `agent: "claude"`; the herdr-dev stub answers `{}` to unknown verbs.
**Reasoning**: each finding named its fix and no fix changes a criterion; leaving them in the reports alone would hand `/code` a plan that fails as written.
**Alternatives rejected**: a third review round on the lane's own call (step 20 forbids it); shipping the plan with the defects noted only in the reports.
**Trade-off accepted**: these repairs have had no reviewer pass.

### P5. Plan review round 3 rulings (lane session, 2026-11-22)

Round 3 was scoped to the P4 repairs on agent-evals-c3's ruling. Result: 0 BLOCKER, 2 GAP, 9 NIT across both shards; every round-2 BLOCKER and GAP confirmed fixed. All eleven are written into the spec:

1. GAP (shard A) Phase 4 §1 step 6 and §2: a failed `git add` of the rebuilt pages keeps today's stop text (exit 1, "could not stage the rebuilt pages", add command, saved text, ref); the test at line 770 moves to `put_back_by_hand` instead of being deleted. Only line 803 (the `stash apply` mock) is deleted.
2. GAP (shard B) Phase 7 §2: the no-sender stub is a Python file written with `write_text`, branching on `sys.argv[1]`. Same wording added to Phase 1 §5 for the stub lanes CLI (shard A NIT).
3. NIT Phase 1 Manual: probe lane list is Phases 6 to 10; Phase 10 closes it. Brief pinned as a no-op ("Reply ok and stop. Edit nothing, commit nothing.").
4. NIT Phases 1, 7, 10 Manual: variables are exported in each Bash call, never a command prefix.
5. NIT Phase 10 Manual: wait for `agent_status` other than `working` before `--close`.
6. NIT Phase 5 §1: `<branch>` in the fetch ref is the merge ref's last component; a remote that fails `git check-ref-format` (`.` or a URL) exits 1 "nothing pulled or set aside".
7. NIT Phase 12: diff check counts `^tests/scripts/test_`.
8. NIT Phase 3 §2: the hook fires on `set_aside`'s `reset --hard`, so the pull refuses; the test asserts only the failed put-back and the ref.
9. NIT Phase 4 §1: page excludes use `:(exclude,literal)`.
10. NIT Phase 4 §2: one step-1 test (line 159, file `k`) and one step-3 test (line 179, file `g`).
11. Shard B note: `STUB_HERDR_API` records `agent get` targets so Phase 6's assertion can be made.

**Trade-off accepted**: these fixes have had no reviewer pass; every one is wording that pins a choice the reviewer traced, not a new mechanism.

## Direction & Constraints

- Research is ground truth over the ticket: `herdr-worktree` and `herdr-worktree-prune` live in `scripts/.local/bin/`, not `claude/.claude/scripts/tools/`; only `pull_keep_index.py` is under `claude/.claude/scripts/tools/`.
- No merge-line generator exists. "The lane merge line" is a `!` line the main session writes by hand from CLAUDE.md / orchestration.md prose.
- Nothing persists a lane's brief or fork session id today beyond the `mktemp` file herdr-dev deletes and the text in `herdr-worktree-watch.log`. The fork's session id is known only to the watcher, up to 120 s after lane start, and rotates on every `/clear`.
- herdr 0.8.2: `herdr <group> <verb> --help` prints top-level help; use `herdr <group> help <verb>`. Verified forms: `herdr worktree open [--workspace ID | --cwd PATH] (--path PATH | --branch NAME) [--label TEXT] [--focus]`; `herdr agent start <name> --kind KIND --pane ID [--timeout MS] [-- <agent-args...>]`; `herdr agent rename <target> <name>|--clear`; `herdr pane rename <pane_id> <label>|--clear`; `herdr agent get <target>` (unique agent name or pane id). herdr agent names match `[a-z][a-z0-9_-]{0,31}` and clear on exit, so they can never stand for a ListAgents name.
- `/tmp` is tmpfs with a per-user `usrquota`; `df` reports the whole tmpfs and cannot see the quota that ran out.
- Lane worktree liveness: today's prune would remove a dead lane with zero own commits and a clean tree (tip is an ancestor of origin/default) and delete its branch. An open lane entry must count as alive in the prune (false destruction is worse than a leak).
- pull_keep_index: the built-page failure's likely cause is `staged_clash_paths` holding non-page files the pull also changed, so the no-index route was skipped and `exit_unapplied` left a clean tree. `--help` is taken as the repo path. The save commit has no ref. Ubuntu 22.04 git 2.34 lacks `merge-tree --write-tree`.
- Lane worker rule: this lane never edits CLAUDE.md, settings.json or orchestration.md; proposed lines go to agent-evals-c3.
- Owners ruling: the ask to add `row_for_name` and a lane-files line to the Owners list in `claude/.claude/scripts/CLAUDE.md` was refused. The owners are stated in the docstrings of `lib/lane_entries.py` (lane files and lane lock) and `session_registry.row_for_name` (name-to-live-row lookup) instead. Ruled by agent-evals-c3 (orchestrating session), 2026-11-22; agent-evals-c3 reports this follows the user's Owners ruling (not a typed sign-off seen by this run).
- Accepted: `entry_containing` uses `script_utils.path_is_under`; plan section 1 reworded to match. agent-evals-c3, 2026-11-22.
- Phase 0 ticked on the round-4 review PASS and a green full check, despite the review cap. agent-evals-c3, 2026-11-22.
- Phase 12 gate: the five asks were accepted by the /code session, 2026-11-22. Ask 2 (update the remote-tracking ref after `fetch_tip`) was shown wrong: git 2.56.1 already updates it, so the guard test stays and no `update-ref` is added.
- The lane's history was rebased onto origin/master after the 2026-11-22 rewrite, by fast-forward push and no force (agent-evals-c3, 2026-11-22). Phase 2's hunk-review-pane change and Phase 4's item were already on master; see the plan's Plan Deviations.
