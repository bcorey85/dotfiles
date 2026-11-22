# Plan review round 1, shard A (plan-reviewer, 2026-11-22)

DUCK     Phase 0: adds `lib/lane_entries.py` (lane-file grammar, locked atomic writes), the `tools/lanes.py` CLI (add / set-session / remove / get / get --containing / list / check) and `session_registry.row_for_name`, with tests.
DUCK     Phase 1: adds `session_pane.py sender`. `herdr-worktree --fork` pipes the brief to `lanes.py add`, the watcher calls `set-session` with the fork id and its recovery log names `herdr-lane-resume`, and `herdr-phase-change` writes the post-/clear id and the sent prompt to the lane that holds the target's cwd.
DUCK     Phase 2: `hunk-review-pane` runs `herdr-api pane rename $HERDR_PANE_ID review` after the guard at lines 74-78 and before the `mkdir` at line 81. A failed rename warns and the script goes on. Adds a stub-herdr test and a line in hunk.md.
DUCK     Phase 3: `pull_keep_index.py` gets `--help`, plus a `refs/pull-keep-index/<stamp>-<sha8>` ref made between `stash create` and `reset --hard`. The ref is threaded into every saved/recovery message and deleted after its own successful put-back.
DUCK     Phase 4: replaces `put_back_without_index` with a six-step repair: staged diff without the pages through `apply --index --3way`, `write-tree`, unstaged diff through `--3way`, `read-tree`, the configured driver run once per page, then `git add` the pages. Adds incident-shape tests and one run by hand against the real driver.

GAP      Phase 4 §3 (real-driver run, the AC31 evidence)  As written, the scenario never builds a page clash, or else it fails its own pass check
         Evidence: plan: "in `driver-b` add a change file with `build_changes.py new`, build, commit, push; in `driver-a` add a different change file, build, stage it…". `~/agent-evals/bin/build_changes.py:98`: "`new` writes an unfilled note … the note fails validation until its kind, description, evidence and sections are filled". `build_changes.py:663-667`: an untracked unfilled note is "left out" of the build.
         Reading: if the coder follows the steps literally, each build leaves its own new note out. The pages do not change on either side, so no built page clashes and the run exits 0 without ever reaching `put_back_by_hand`. Once driver-b commits its stub, the note is tracked but still unfilled: the driver hits its `PickedFileProblem` (exit 1), and `build_changes.py --check` fails. The step has to say that both notes are filled with valid frontmatter and sections before building. It should also assert that the pages actually changed on both sides.

GAP      Phase 1 Manual Verification and Phase 2 Manual Verification  Both checks run the master copies, not this worktree's
         Evidence: `readlink -f ~/.claude/scripts` -> `/home/brandon/dotfiles/claude/.claude/scripts`. `readlink -f ~/.local/bin/herdr-worktree` -> `/home/brandon/dotfiles/scripts/.local/bin/herdr-worktree` (~/dotfiles is on `master`). `zsh/.zshrc:277` `alias hw='hunk-review-pane'` resolves through ~/.local/bin to master as well. Plan line 214: "`herdr-worktree --fork …` then `python3 ~/.claude/scripts/tools/lanes.py get <basename>`". Line 247: "run `hw`".
         Reading: Phase 1's check calls the master herdr-worktree, which writes no entry, and a `lanes.py` that does not exist until merge, so the coder gets stuck. Phase 2's `hw` runs the unchanged master script, and the pane never gets the label. Neither step says to run the worktree copy by path with `HERDR_LANES_CLI` / `HERDR_SESSION_PANE` pointed at the tree.
         Enumerated: grep of the shard's Manual/Agent-run steps for stowed paths (`~/.claude/scripts`, bare `hw`) -> 2 (lines 214, 247). Phase 4 §3 uses the absolute worktree path correctly.
         Evidence-class: declared-only (plan Constraints line 69 names the env overrides; they do not exist in the tree yet)

GAP      Phase 1 §3 (watcher recovery text)  The new recovery log can be read two ways, and when no lane entry exists it names a command that cannot work
         Evidence: "Recovery text with a session id becomes `1. herdr-lane-resume <name>`; the no-session-id steps stay." Test: "`recovery_lines` reads `1. herdr-lane-resume repo-fork`". Today `recovery_lines` (test_herdr_worktree_watch.py:50-55) returns three lines: step 1, step 2 (`herdr-dev … <ws> s1 …`) and the `<ws>` note. The tuios variant test is at line 263. P2.4: "a failed lane-file write warns … and the fork starts".
         Reading: one coder replaces all three lines with the one `herdr-lane-resume` line, under herdr and under tuios. Another coder swaps only step 1 and keeps step 2 and the note. The plan also gives no rule for a fork whose `lanes.py add` failed (allowed by P2.4) or whose watcher `set-session` failed ("logging a failure"). In both cases the log still says `herdr-lane-resume <name>`, and per Phase 8 (1) that command exits 1 with "no entry". The old herdr-dev steps, which would have worked, are gone.

GAP      Phase 3 §1 (`--put-back` with a bare hash)  When the argument is a bare hash there is no ref for the messages to name
         Evidence: "`saved_text(saved, ref)` reads 'The local changes are saved in <saved> (ref <ref>)'"; "`--put-back` accepts a ref or a hash … deletes the ref on success only when the argument was a ref under the prefix". AC25: "Every message that names the saved changes also names their ref". AC15: "never leaves the edits only in an unreferenced commit".
         Reading: reading A makes a new ref for the hash before the apply, so a failed put-back keeps a named ref; this satisfies AC15/AC25 but leaves a ref behind on success unless it is deleted then. Reading B passes `ref=None` and prints the message without a ref, which breaks AC25. Both follow the plan. The plan also never says whether a ref argument is resolved to a hash before it goes into `stash apply`, `BUILT_PAGE_STASH` and `update-ref -d <ref> <saved>`.

GAP      Phase 4 §1 (step 1 and step 3 conflict route)  The failure message reused from `exit_unapplied` misdescribes the tree at that point
         Evidence: plan: "on conflict `exit_unapplied(repo, saved, left_out=pages)` naming the ref … (3) … same failure route". pull_keep_index.py:313-320, exit_unapplied's text: "The other files are back, staged or unstaged as before. … Then stage the pages: git add -- <pages>".
         Reading: a conflict at step 1 stops before step 3, so the unstaged diff was never applied and the unstaged edits are missing from the tree. No page has been rebuilt either, because step 5 never ran. The coder ships a message that says every file is back and tells the user to `git add` pages still at HEAD. The ref keeps the work, but the stated state is wrong. A conflict at step 3 has the same problem with the pages. The plan needs a route that says which parts were applied and that the pages still need a rebuild.

GAP      Phase 1 Manual Verification vs Phase 8 Manual Verification  The plan contradicts itself about the probe lane
         Evidence: Phase 1 line 214: "Remove the probe lane afterwards." Phase 8 (spec.md:436): "on the Phase 1 probe lane, close its workspace, run `herdr-lane-resume <name>` …".
         Reading: if the Phase 1 coder removes the lane as told, Phase 8's agent-run check has no lane to run against. If the lane is kept for Phase 8, Phase 1's own instruction is not followed.

NIT      Phase 1 §4  The stored `brief` is "the sent prompt", which includes the `[from orchestrator pane <id>]` prefix (and, after Phase 7, the report-to marker). On resume, `herdr-lane-resume` replays a pane id that may no longer exist. The plan is explicit ("`brief` equals the sent text"), so this is a choice, but the resume path inherits a stale prefix.

NIT      Phase 2 §1  "Ensure `export PATH="$HOME/.local/bin:$PATH"`" contradicts the script header at hunk-review-pane:23 ("Env (PATH shims, EDITOR) is the caller's job"), and the plan does not edit that line. The new test has to set `HOME` to a temp folder, as test_herdr_phase_change.py:75 does; otherwise the real `~/.local/bin/herdr-api` shadows the stub. The plan's test description does not mention this.

NIT      Phase 0 §2  `file_lock.LockTimeoutError` (file_lock.py:12) has no exit code or message in the `lanes.py` contract. Only `LaneFileError` → exit 2 is specified, so the bash callers' "failed add/set-session" paths will see whatever traceback the coder leaves.

NIT      Phase 0 §4  The CLI `tools/lanes.py` is tested inside `test_lane_entries.py`. docs/toolkit-script-rules.md puts tests in `tests/scripts/test_<script>.py`, which would be `test_lanes.py` for the CLI.

Claims about the tree that I checked and found to hold:
- herdr-worktree: variables `label`, `worktree`, `main_checkout`, `branch`, `prompt` (lines 58-192); `ws` known at line 210; herdr-dev called at line 253; recovery header at lines 31-47.
- herdr-phase-change: `agent get` and `new_session`; the final prompt is the last line.
- herdr-worktree-watch: polls the session id, then writes the log.
- hunk-review-pane: guard at lines 74-78, `mkdir` at line 81.
- `.claude/rules/hunk.md` exists.
- The test files named in the shard all exist, and so do `stubs.write_stub` and `toolkit_paths.TOOLS_DIR`.
- session_registry provides `live_session_rows`, `other_live_session_in` (a None id matches the caller's own row), `holder_label` and `session_display_name`; `row_for_name` does not exist yet.
- `file_lock.hold_exclusive(lock_path, timeout_seconds)`; `script_utils.write_text_atomically` (its temp files end in `.tmp`) and `git_output`; `hook_input.claude_code_temp_root`; `process_group.pid_is_alive`.
- pull_keep_index provides `saved_text`, `recovery_text`, `set_aside`, `listed_paths`, `staged_tree`, `restore_the_split`, `staged_clash_paths`, `built_page_paths`, `built_page_driver_configured`, `put_back_without_index`, `exit_unapplied`, `put_back` and `page_stage_arguments`.
- Test `test_a_staged_clash_on_a_built_page_and_an_ordinary_file_stops_with_the_put_back_command` exists at line 159.
- The prune script is 949 lines and provides `World`, `Keep`, `CANNOT_CHECK`, `real`, `inside` and `remove_one`.
- `.gitattributes` marks six pages `merge=built-page`, and this repo configures `merge.built-page.driver` as stated.
- The driver docstring confirms it reads `BUILT_PAGE_STASH` and checks the stash parent, HEAD and the stash.
- `build_changes.py` has `--check` and `new --by --root`.
- Not settled, because the subjects are outside the tree: the herdr 0.8.2 CLI fields and `claude --resume` behaviour.

VERDICT: NEEDS CHANGES (0 blocker, 6 gap)
