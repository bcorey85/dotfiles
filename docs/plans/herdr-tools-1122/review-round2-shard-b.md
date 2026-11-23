# Plan review round 2 (DEEP), shard B: verification pass, 2026-11-22

DUCK     Phase 5: Holds a lock (seconds from `PULL_KEEP_INDEX_LOCK_SECONDS`) over the whole dispatch, `--put-back` included. When the checkout is shared and dirty, `shared_pull` fetches, then either says "already held", refuses on a diverged branch, refuses on overlapping files, or fast-forwards with `merge --ff-only` and runs `set_upstream`. Nothing is set aside on any of these paths.
DUCK     Phase 6: Adds `session_pane.py resolve` (directory, then registry name, then the target as given). herdr-phase-change uses `$session_pane`, which Phase 1 §4 defines.
DUCK     Phase 7: herdr-phase-change reads the sender JSON safely under `set -e`, exits 1 with the reason when no sender name comes back, and otherwise adds the report-to marker.
DUCK     Phase 8: Adds `herdr-dev --resume`. `herdr-lane-resume` resumes a lane. `--close` refuses while an agent is working, then closes the workspace, polls until the agents are gone, removes the entry and runs the prune.
DUCK     Phase 10: The prune gains an `open lane` keep. It reads the lanes CLI path with `expanduser`, both `setUp` methods are covered, and it fails closed when the lane list cannot be read.
DUCK     Phase 11: Full suite, lint, page rebuild, and a ban grep for `put_back_without_index` only.
DUCK     Phase 12: /close-branch, with a check on how many test files the diff holds.

## Prior findings (round 1, shard B)

- BLOCKER, the Phase 11 ban grep matches the plan's own files — **FIXED.** I ran the new grep as written: `rg -n --hidden "put_back_without_index" claude opencode scripts docs/changes/*.md` exits 0 with 2 hits, both in one file: `claude/.claude/scripts/tools/pull_keep_index.py:286` (the def) and `:338` (the call). Phase 4 deletes that function. `docs/changes/*.md` has 0 hits, and `docs/plans/` and `docs/changes/notes/` are no longer searched. After Phase 4 lands the ban can pass, and it can still fail.
- BLOCKER, `--close` leaves the worktree behind — **FIXED in the design.** Phase 8 §2 step 3 now closes the workspace and polls the agent list before the prune. That clears both keep conditions in `check_herdr` (herdr-worktree-prune:591-605). The end-to-end proof is still missing; see GAP 2.
- GAP, a 300 s lock makes the test slow, and `sleep` cannot hold a lock — **FIXED.** The timeout comes from the env var, the test uses `=1`, and the holder is a Python child running `file_lock.hold_exclusive` that prints `held`.
- GAP, the keep-in-tree RED could not fail — **FIXED.** The hook now logs `kept=1/0` from `grep -q local-edit`. Before the change, the solo route's `reset --hard` drops the edit before the rebase moves `refs/heads/`, so the hook logs `kept=0`. After the change, `merge --ff-only` updates the work tree before the ref, so the hook logs `kept=1`.
- GAP, the "ahead" check and the fetch order on a `target` pull — **FIXED.** The fetch comes first, then FETCH_HEAD is read. `@{u}` is never read, so a `pull_target` that returns `[]` is covered. `set_upstream` runs on both success routes. These match the tree: `pull_target` returns `[]` at 372/377/387, `upstream_relation` fetches only when a merge ref is set (166-171), and `set_upstream` is at 411.
- GAP, `--put-back` ran outside the lock — **FIXED.** "The whole dispatch, `--put-back` and the pull alike", resolved through `--git-common-dir`, and a test covers `--put-back` while the lock is held.
- GAP, the tool-path variables were never defined — **FIXED.** Phase 1 §4 defines `lanes_cli` and `session_pane` right after `export PATH` (herdr-phase-change:24) and bans the inline form. In Phase 7, the `|| true` and `|| sender=""` guards survive `set -euo pipefail` (line 23), and `jq` on empty input exits 0.
- NIT, the two `setUp` methods and `expanduser` — **FIXED.** Both `setUp` methods are at lines 263 and 1162, as stated, and the plan now uses `os.path.expanduser`.
- NIT, the herdr-dev stub list — **PARTIAL.** It still leaves out calls the script makes under `set -e`:
  - `pane current` (herdr-dev:51)
  - `pane resize` (100, 136)
  - `tab create` (140)
  - `tab focus` (145, 165)
  - `pane focus` (166)

  A stub that answers `{}` to any unknown verb covers all of them.
- NIT, the Phase 12 diff check could not fail — **PARTIAL.** See the NIT below.

## Round-1 shard A findings that reach this shard

- GAP, manual checks run the stowed master copies — **PARTIAL.** Phase 8's manual check now uses the worktree path and the two variables. The same defect remains in Phases 6, 7, 9 and 10; see GAP 2.
- GAP, the Phase 1 and Phase 8 probe lanes contradict each other — **FIXED.** Phase 1 now says "Keep the probe lane open", and Phase 8 ends it.

## New findings

GAP      Phase 7 §2 no-sender test, against Phase 6 §2: the stub `session_pane.py` also answers `resolve`, which runs first, so the test fails before it reaches the sender check.
         Evidence: Phase 6 §2 runs `resolved=$(python3 "$session_pane" resolve "$target") || exit 1` "after argument parsing". Phase 7 §1 runs `sender` "before the status check", and the status check is the `agent get` at herdr-phase-change:65, so resolve comes first. Phase 7 §2: "a stub `session_pane.py` printing `{"name": null, "reason": "no session"}` and exiting 1 → exit 1, stderr shows `(no session)`".
         Reading: a coder who writes the stub as described (one fixed output, exit 1) gets `resolve` exiting 1, and herdr-phase-change exits through `|| exit 1` with no `(no session)` on stderr. Exit 1 and "zero prompts" still pass, but the stderr assertion fails. The likely fix: the stub has to branch on `$1`, printing `{"pane_id": ..., "via": "as-given"}` for `resolve` and the null-name JSON for `sender`. The plan does not say so.

GAP      Manual Verification in Phases 6, 7, 9 and 10 runs the stowed master copies. Phase 10's check also needs a merged probe lane that no step creates. That leaves AC9 and the Phase 10 Success Criterion ("closes its workspace, then removes its worktree") with no proof that can run.
         Evidence:
         - `~/.local/bin/herdr-phase-change` and `~/.local/bin/herdr-worktree-prune` link to `../../dotfiles/scripts/...`, and `/home/brandon/dotfiles` is on `master`.
         - `~/.local/bin/lane-status`, `~/.local/bin/herdr-lane-resume` and `~/.claude/scripts/tools/session_pane.py` do not exist.
         - Shard lines 176 (`python3 ~/.claude/scripts/tools/session_pane.py resolve`), 213 (`herdr-phase-change <lane>`), 278 (`lane-status; echo $?`) and 308 (`herdr-worktree-prune` dry run and `herdr-lane-resume --close` with no path).
         - Phase 8's manual check ends with "The probe lane ends here", so no lane is left to close.
         - The real lane store holds no entries made by this branch, so "lists every lane worktree with an open entry" is true when there are none.
         - Phase 8 tests stub `herdr-worktree-prune`, and Phase 10 tests never run `--close`.
         Reading: the coder gets "No such file" (Phases 6, 9 and 10) or runs master's unchanged herdr-phase-change (Phase 7). Phase 10's check cannot be done: no lane entry, no merged probe lane, and a master prune with no `open lane` keep. Nothing runs `--close` against the real prune with a closed workspace, which is the round-1 BLOCKER 2 path. Each step needs the worktree path plus `HERDR_LANES_CLI` and `HERDR_SESSION_PANE`, as Phase 8 now has. Phase 10 also needs a step that makes and merges a probe lane in a scratch clone, or an automated test that runs `herdr-lane-resume --close` against the real prune copy.
         Enumerated: grep of shard B's Manual Verification lines for `~/.claude/scripts` or a bare stowed command -> 4 (lines 176, 213, 278, 308).

NIT      Phase 12 Automated Verification: the check uses `>= 9`, but phases 0-10 name 13 test files. Six are edits (session_registry, herdr_phase_change, herdr_worktree, herdr_worktree_watch, pull_keep_index, herdr_worktree_prune) and seven are new (lane_entries, lanes, session_pane, hunk_review_pane, herdr_dev, herdr_lane_resume, lane_status). The check passes with four of them missing, so the note "every phase 0-10 test file is in the diff" is not what it tests.
         Enumerated: `[ -f tests/scripts/test_<t>.py ]` over the 13 names -> 6 exist, 7 new.

NIT      Phase 11 ban: the built pages render each note's description (for example `docs/changes/changelog.md:56`). If Phase 4's change note says "replaces `put_back_without_index`", the rebuilt `changelog.md` carries the name and the ban fails on the plan's own work. Phase 4's change file should not name the removed function.

NIT      Phase 5 §1: `shared_pull` reads `FETCH_HEAD` after its own fetch. The lock excludes only other pull_keep_index runs, so a plain `git fetch` from another session in the same worktree can rewrite FETCH_HEAD between the two steps. Running `rev-parse` on the fetched ref, or fetching into a named ref, would close the window.

NIT      Phase 6 §3 and Phase 7 §2: registered rows need a live `pid` (`live_session_rows` checks `pid_is_alive`, session_registry.py:48-50), and resolve filters `agent == "claude"`. Phase 5 states the live-pid requirement (`sleep 600` child), but the Phase 6 and Phase 7 test setups do not, and the Phase 6 stub agent list does not say it carries `agent: "claude"`.

Claims settled against the tree:
- pull_keep_index.py is 478 lines. `main` order: `--put-back` returns at 427-436, then `stopped_rebase_dir` at 442, `upstream_relation` at 446, `pull_target` at 451, `set_aside` at 457, `set_upstream` at 473-474.
- `listed_paths(repo, *diff_arguments)` is at 214. `file_lock.hold_exclusive` and `LockTimeoutError` are as described.
- `other_live_session_in` and `holder_label` exist (session_registry.py:54, 69).
- herdr-worktree-prune is 949 lines. `World(...)` is built at 471, `check_default` is at 512, `check_herdr` at 591-605, `CHECKS` at 608 and `remove_one` at 699.
- The prune test `setUp` methods are at 263 and 1162.
- herdr-phase-change has `set -euo pipefail` at 23, `export PATH` at 24, `agent get` at 65, and `agent prompt` at 78 and 94.
- The herdr-dev line numbers in the Phase 8 stub list (61, 68, 108-109, 131) match. I cannot settle the herdr 0.8.2 `workspace close` verb or the shim's `workspace list` shape, because both are outside the tree.

VERDICT: NEEDS CHANGES (0 blocker, 2 gap)
