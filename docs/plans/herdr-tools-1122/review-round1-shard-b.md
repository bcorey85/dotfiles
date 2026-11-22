# Plan review round 1, shard B (plan-reviewer, 2026-11-22)

DUCK     Phase 5: In a shared, dirty checkout, pull_keep_index fast-forwards in place, or refuses with the files named. It holds a flock on `<common dir>/pull-keep-index.lock` for 300 s, and tests pin a writer that changes a file mid-pull.
DUCK     Phase 6: Adds `session_pane.py resolve` (directory → registry name → as given). herdr-phase-change swaps its target for the resolved pane id.
DUCK     Phase 7: herdr-phase-change looks up the sender name and adds ` [report to session X]` to every prompt; with no name it exits 1.
DUCK     Phase 8: Adds `herdr-dev --resume`, which drops `--fork-session`, and a new `herdr-lane-resume <name>` / `--close <name>`. `--close` runs `herdr-worktree-prune --apply` in the main checkout.
DUCK     Phase 9: Adds `lane_status.py` and a `lane-status` wrapper that report memory, scratch df/du and lanes that are not working; exit 0/1/2.
DUCK     Phase 10: The prune gains an `open lane` keep, fed by `lanes.py list` and fail-closed, inserted after `check_default`.
DUCK     Phase 11: Full suite, lint, rebuilt change pages, a ban-grep for stale names, and lines handed off for CLAUDE.md and orchestration.md.
DUCK     Phase 12: /close-branch review pass and recap.

BLOCKER  Phase 11 Automated Verification, ban grep  The ban cannot pass: it matches the plan's own files and history pages.
         Evidence: criterion `rg -n "put_back_without_index|herdr-worktree-watch.log" claude opencode scripts docs` (ban: no match). Running it now gives 14 hits: docs/plans/herdr-tools-1122/spec.md:3 (the criterion text itself, plus Phase 4's "replaces `put_back_without_index`"), 03-decisions.md:1, 02-research.md:6, docs/plans/coder-worktree-fixes/plan.md:2, docs/changes/notes/2026-11-10-herdr-worktree-watches-a-forked-workspace-and-logs.md:2. None of the hits is in claude/, opencode/ or scripts/. Step 1's wider pattern (`herdr-dev <worktree> <ws>|...`) also hits coder-worktree-fixes/{plan,acceptance-criteria,00-ticket}.md and the same change note.
         Reading: The plan says "any hit is fixed". A coder who follows it rewrites this plan, older plans and a past change note to make the ban pass. A coder who does not gets a criterion that fails forever. The search roots need to leave out `docs/plans/` and `docs/changes/notes/`, or narrow to the code trees.
         Enumerated: rg -c "herdr-worktree-watch.log|put_back_without_index" claude opencode scripts docs -> 14 hits in 5 files, 0 in claude/opencode/scripts

BLOCKER  Phase 10 / Phase 8 `--close`  On the usual close, the lane's own worktree is not removed, so AC9 and Phase 10's own success criterion fail.
         Evidence: Phase 10 success criterion: "Closing a merged lane removes its worktree". `--close` only does `lanes.py remove` and then the prune. It never closes the lane's herdr workspace and never stops its agent. The prune's `check_herdr` (scripts/.local/bin/herdr-worktree-prune:590-605) keeps a tree when "herdr workspace ... carries this folder's name" or "a herdr agent works inside it". The workspace list is read fresh in `build_world` (line 471).
         Reading: The orchestrator closes a lane right after it merges, while the lane's workspace and idle claude agent are still open. The prune then keeps that tree as `herdr`, so the worktree count is not "the count of unmerged or dirty lanes" (AC9). The tree goes only on some later `--close` that happens after the user has closed the workspace by hand. The plan never says whether `--close` closes the workspace first or tells the user to. The Phase 10 manual check, a "merged probe lane", does not settle it either.

GAP      Phase 5 Tests, lock test  The 300 s timeout makes the AC28 test take 5 minutes, or forces a knob the plan never names.
         Evidence: `file_lock.hold_exclusive(<common dir>/pull-keep-index.lock, 300)`; the test "exits 1 within the test timeout naming the lock". claude/.claude/scripts/lib/file_lock.py:17-30 polls until the deadline. The existing test_pull_keep_index.py subprocess calls pass no `timeout`.
         Reading: Reading A: the test waits the full 300 s inside the 600 s runner cap. Reading B: the coder adds an env override for the timeout that the plan does not name. Also, "a `sleep` child holds the lock" is not possible on its own: `sleep` cannot hold an flock. The holder has to be `flock(1)` (util-linux, not on stock macOS) or a Python child, and the plan does not say which.

GAP      Phase 5 Tests, keep-in-tree RED signal  The `exists=1` check passes before the change, so the stated RED is wrong.
         Evidence: "log shows `exists=1`" and "RED before: keep-in-tree test logs `exists=` empty". `set_aside` (pull_keep_index.py:195-207) runs `stash create` and then `reset --hard`. A tracked, modified `bin/x` still exists after that reset, so `test -f bin/x` prints 1 before the change too.
         Reading: If `bin/x` is a tracked, modified file, the exists check can never fail. The test only goes red by accident, through the put-back clash with the hook's "writer" text. If `bin/x` is untracked, `status --porcelain --untracked-files=no` reads the tree as clean and the shared route never runs. The hook has to log the content, for example whether the dirty edit is present, not whether the file exists.

GAP      Phase 5 Changes, the "ahead" and fast-forward steps for a `target` pull  It is not defined which ref to compare and merge, or when to fetch.
         Evidence: "`ahead = rev-list --count @{u}..HEAD` (`FETCH_HEAD..HEAD` for a `target` pull); not ahead → fetch then `git merge --ff-only <upstream>`".
         Reading: For a `target` pull, FETCH_HEAD does not exist until the fetch runs. `upstream_relation` returns early when there is no merge ref (pull_keep_index.py:166-168), so it never fetched. The text orders "ahead" before "fetch", so one coder fetches first and another reads a missing or stale FETCH_HEAD. Two more cases are open:
         - `pull_target` returns `[]` when `@{u}` does not resolve but the remote has the configured ref (lines 383-388). Then `@{u}..HEAD` fails, and the plan names no route.
         - The shared fast-forward success "exits 0" and never reaches `set_upstream` (lines 473-474). A targeted first pull then leaves no upstream set, unlike the solo route.

GAP      Phase 5 lock scope vs AC28  `--put-back` runs outside the lock.
         Evidence: "The run from `stopped_rebase_dir` to the end sits in `with file_lock.hold_exclusive(...)`". In `main`, the `--put-back` branch returns at pull_keep_index.py:427-435, before `stopped_rebase_dir` at line 442.
         Reading: AC28 says "never run their set-aside and put-back at the same time". A `--put-back` run alongside a normal pull is not excluded, and the plan says nothing on whether it should be.

GAP      Phases 1/6/7, herdr-phase-change  The plan names the tool paths three different ways.
         Evidence: Phase 6: `python3 "${HERDR_SESSION_PANE:-$HOME/.claude/scripts/tools/session_pane.py}" resolve`, written inline. Phase 7: `python3 "$session_pane" sender`. Phase 1: `python3 "$lanes_cli" get --containing`. scripts/.local/bin/herdr-phase-change defines neither `session_pane` nor `lanes_cli`, and no phase says to add them.
         Reading: The script runs `set -euo pipefail` (line 23), so following Phase 7 literally dies with an unbound variable. The coder has to guess where to define both variables and whether Phase 6's inline form should switch to the variable. Phase 7 also never says how `<reason>` gets into the message: under `set -e` with pipefail, a bare `sender=$(... | jq ...)` exits without printing it.

NIT      Phase 10 Tests  "`setUp` sets `XDG_STATE_HOME` ... and `HERDR_LANES_CLI`". tests/scripts/test_herdr_worktree_prune.py has two `setUp` methods (lines 263 and 1162). Existing tests run with a temp HOME, so a missed setUp turns every tree into `cannot check`. Separately, `${HERDR_LANES_CLI:-~/.claude/...}` is bash syntax inside a Python script, and `~` needs `expanduser`.

NIT      Phase 8 Tests, herdr-dev stub  The stub lists `workspace get`, `pane list`, `pane split`, `pane wait-output`, `pane send-text`. herdr-dev also calls `tab rename`, `pane rename` (lines 108-109, 131), `pane send-keys` (61, 68) and the console-tab calls (around 141-144). All of these need stub answers.

NIT      Phase 12 Automated Verification  `test -n "$(git diff --name-only 8436be97..HEAD)"` is true after any commit on the branch, so it cannot fail.

Claims settled against the tree:
- herdr-worktree-prune is 949 lines.
- `World(...)` is built at line 471.
- These exist in the prune: `World`, `Keep`, `CANNOT_CHECK` (89), `real` (213), `inside` (217), `check_default` (512), `CHECKS` (608), `remove_one` (699).
- These exist in pull_keep_index.py: `stopped_rebase_dir` (75), `set_aside` (195), `target` (451), `put_back_without_index` (286).
- session_registry.py has `other_live_session_in` (54), `holder_label` (69) and `session_display_name` (76). `row_for_name` is absent; Phase 0 creates it.
- file_lock.py has `hold_exclusive` and `LockTimeoutError`. hook_input.py has `claude_code_temp_root` (281). process_group.py has `pid_is_alive`.
- tests/scripts has stubs.py `write_stub`, toolkit_paths.py, tests/lint.sh and tests/parallel_tests.py.
- test_herdr_dev.py is absent (correct, the plan calls it new). orchestration.md lines 35-36 match the plan's description. .claude/rules/hunk.md exists.

VERDICT: NEEDS CHANGES (2 blocker, 5 gap)
