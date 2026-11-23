# Plan review round 2, shard A (verification pass, 2026-11-22)

Plan: /tmp/plan-review-shards-zr8xvqbf/review-shard-a.md (an extract of /home/brandon/dotfiles-herdr-tools-nov22/docs/plans/herdr-tools-1122/spec.md)

## Round-1 findings: verdicts

Shard A:
- GAP Phase 4 §3 (the real-driver scenario never builds a page clash): **FIXED.** Both notes are now filled and checked before the build. Each side asserts that `changelog.md` changed, and the pass check greps for both probe titles. Checked: `build_changes.py new --help` accepts `--by` and `--root` after the title. `install_merge_driver.py [repo]` exists, and `.gitattributes` line 1 names it. `install/stow` has 136 lines, so an edit at line 2 and an edit at the end do not overlap.
- GAP Phase 1/2 Manual Verification ran the master copies: **FIXED.** Both now run the worktree copies by absolute path. herdr-worktree runs `detach`, `herdr-worktree-watch` and `herdr-dev` from `$bin_dir` (herdr-worktree:54, 110, 253, 271). `detach` uses `exec setsid`, so the environment carries over.
- GAP Phase 1 §3 (two ways to read the watcher's recovery text): **FIXED** for the text itself. When `lane_session` is set, the log gets exactly two lines. When it is empty, today's lines stay. Repaired §3 introduces a new defect, below (GAP 4).
- GAP Phase 3 §1 (`--put-back` with a bare hash): **FIXED.** The argument is resolved once. The plan gives the order for picking a ref (prefix, then `--points-at`, then `keep_ref`), picks it before the clean-tree check, and defines `drop_ref`.
- GAP Phase 4 §1 (the `exit_unapplied` text was wrong for a step 1 or step 3 conflict): **FIXED** by the new `exit_rolled_back` route. Two new defects sit in the same step text (BLOCKER 1 and BLOCKER 2).
- GAP probe-lane contradiction: **FIXED.** Phase 1 keeps the lane. Phase 8 (spec.md:461) resumes it, closes it and deletes the scratch clone.
- NITs: the LockTimeoutError exit is fixed. The test split is fixed. The PATH line is fixed. The brief prefix is now an accepted choice.

Shard B items that touch this shard:
- GAP: herdr-phase-change named its tool paths three different ways. **FIXED.** Phase 1 §4 defines `lanes_cli` and `session_pane` right after `export PATH` (herdr-phase-change:24). Phase 6 (spec.md:367) and Phase 7 (spec.md:400-403) use those variables. Phase 7 reads `.reason` from the sender's failure JSON, which Phase 1 §1 now prints.
- NIT Phase 12: the criterion could not fail. **PARTIAL.** It can fail now, but it does not check what it claims (NIT below).

## Findings

DUCK     Phase 0: `lane_entries.py` holds the lane-file grammar, with locked atomic writes. `lanes.py` is the CLI over it; a lock timeout exits 2. Adds `row_for_name`. Tests are split into `test_lane_entries.py` (the lib) and `test_lanes.py` (the CLI).
DUCK     Phase 1: `session_pane.py sender` prints JSON when it succeeds and when it fails. A fork adds its lane entry, and the watcher fills `session_id`. When the lane has a session id, the watcher's recovery text becomes one `herdr-lane-resume` line. A phase change writes the new session id and the brief, fail-open.
DUCK     Phase 2: `hunk-review-pane` runs `herdr-api pane rename $HERDR_PANE_ID review` after the guard at lines 74-78, warns if it fails, and changes no PATH. The test uses a temp HOME.
DUCK     Phase 3: adds `--help` and a `refs/pull-keep-index/` ref made between `stash create` and `reset`. `--put-back` resolves its argument to a hash and a ref first. `drop_ref` runs after a successful put-back.
DUCK     Phase 4: `put_back_by_hand` applies the staged diff without the pages, then `write-tree`, then the unstaged diff, then `read-tree`, then runs the driver per page, then `git add`. A conflict at step 1 or step 3 goes to `exit_rolled_back`, which runs `reset --hard`. The real-driver run uses filled notes.

BLOCKER  Phase 4 §1, steps (1) and (3)  `git apply` exits 128 when its input is empty, so the repair fails whenever there are no staged non-page changes or no unstaged changes
         Evidence: plan: "(1) `git diff --binary saved^1 saved^2` with each page excluded, `git apply --index --3way`; on failure `exit_rolled_back(...)`" and "(3) … `git apply --3way`; on failure `exit_rolled_back`". Ran in a scratch repo: `git diff --binary HEAD HEAD | git apply --index --3way` -> `error: No valid patches in input (allow with "--allow-empty")`, exit=128. The same happens with `':(exclude)f'`.
         Reading: when only built pages are staged, step 1 receives an empty diff. When nothing is unstaged, step 3 receives an empty diff. Both are common and both already exist in the tree as tests: test_pull_keep_index.py:179 and :199 stage only page `f`; :199 and :217 have no unstaged edit. Following the plan, the coder sends each of these to `exit_rolled_back` with "conflict … in <no files>". The plan's own tests do not catch this, because the incident shape, `--put-back <ref>` and the real-driver run all have non-empty staged and unstaged diffs. The tempting fix is `--allow-empty`, which arrived in git 2.35. That breaks the stated git 2.34 constraint (spec Constraints, line 66). The step needs "skip the apply when the diff is empty".
         Evidence-class: exercised `git apply` on empty input, git 2.56.1, scratch repo

BLOCKER  Phase 4 §2  The plan says to rename the line-159 test so it asserts success, but its fixture is the step-1 conflict the plan says must exit 1
         Evidence: plan: "Rename `test_a_staged_clash_on_a_built_page_and_an_ordinary_file_stops_with_the_put_back_command` so it asserts success." test_pull_keep_index.py:159-169: `k` is "1\n" at the base, origin pushes "theirs\n", and the user stages "staged\n" alongside the page `f`. That is a whole-line clash on an ordinary file. The same §2 says: "Step 1 conflict (a staged edit to `a` on the line origin changed, plus the page clash) → exit 1, stderr names `a`, 'were not put back'".
         Reading: under the new §1, the line-159 fixture reaches step 1, `apply --index --3way` conflicts on `k`, and the run exits 1. A coder who follows the rename instruction writes a test that can never pass, or bends step 1 to make it pass. Both follow the plan. This test is the step-1 conflict test that already exists, so it should be repurposed as that test, not renamed to success.

GAP      Phase 4 §2  "The other built-page tests keep their behaviour; only message assertions change" is false for four existing tests
         Evidence: test_pull_keep_index.py:179 (an unstaged conflict on `g`) asserts `sorted(status) == ["M  f", "UU g"]`. Under the new route, step 3 conflicts, `exit_rolled_back` runs `reset --hard`, and status is empty. Line 199 (the driver exits 1) asserts `"UU f" in status`. The new step 5 fails after `read-tree`, with `f` at HEAD and no conflict entry. Lines 795 and 816 call `self.module.put_back_without_index(...)`, which §1 deletes, and line 816 mocks `stash apply`, which the new path never calls.
         Reading: the coder has to decide whether to rewrite these as step-3 and step-5 tests or to delete them. The plan says neither and claims they keep their behaviour.
         Enumerated: `grep -n 'put_back_without_index' tests/` -> 2 call sites (795, 816); tests whose asserted status contradicts the new route -> 2 (179, 199); total 4

GAP      Phase 1 §3 and §5  "a failure is written to the log" conflicts with "today's lines stay exactly as they are" and with three exact-log assertions
         Evidence: §3: "run `python3 "$lanes_cli" set-session "$label" "$session"`; a failure is written to the log." §5: "with no entry … the herdr and tuios outputs equal today's three lines". `set-session` exits 1 when there is no entry (Phase 0 §2). test_herdr_worktree_watch.py:94 has `assertEqual(log, "workspace w1 still open\n")`, line 105 has `assertEqual(len(log_text.splitlines()), 4)`, and line 261 has `splitlines()[1]` as step 1.
         Reading: every watcher test that runs with no entry gets an extra failure line in the log, so those three assertions break and §5's "equal today's lines" fails. One coder writes the failure to stderr, which reaches the log only under the launcher. Another appends it to `$log` and edits the three tests. The plan does not say which.
         Enumerated: `grep -n 'assertEqual(self.log.read_text()\|len(log_text.splitlines())\|splitlines()\[1\]' tests/scripts/test_herdr_worktree_watch.py` -> 3

GAP      Phase 0 §1 vs §4  The lane lock file has two names
         Evidence: §1: "Every write: `file_lock.hold_exclusive(<dir>/.lock, 10)`". §4: "exit 2 naming the lock when a Python child holds `lanes.lock`".
         Reading: if the test's child holds `lanes.lock` while the CLI locks `.lock`, the two never contend. The CLI then succeeds and the test fails, or a coder renames one of the two. Separately, the 10 s timeout is not overridable, so the lock test takes 10 s. That is acceptable, but it is unstated.

GAP      Phase 3 §2  The test leans on "the 'would be overwritten' setup", which this phase never defines and which the tree has only as a mock
         Evidence: plan: "a failed put-back (the 'would be overwritten' setup) leaves a ref under the prefix". The only instance in the tree is test_pull_keep_index.py:804, a `mock.patch` of `run_in_repo` that returns success with empty output for every git call and calls `put_back_without_index` directly, so no real ref can exist. The real setup ("Solo route with the hook recreating the set-aside file → put-back fails 'would be overwritten'") is defined in Phase 5 Tests (spec.md:338).
         Reading: the Phase 3 coder either builds on the mock, where the ref assertion cannot be made, or invents a real failing run. The fixture belongs to a later phase.

NIT      Phase 2 §3  The reason given for the temp HOME no longer holds. With no PATH line in the script, the inherited PATH holds the absolute `/home/brandon/.local/bin`, which HOME does not change. The stub wins only because the test prepends its bin dir to PATH, and the plan should say that is the mechanism.

NIT      Phase 1 §3  `label` is set at herdr-worktree-watch:102, after the workspace check. The `set-session "$label"` call, "once the fork's session id is read" (around line 75), needs it moved earlier.

NIT      Phase 1 §4  When `agent get` returns no `cwd`, as the existing phase-change stub does, the plan's literal step runs `get --containing ""`. If `entry_containing` realpaths `""`, it becomes the caller's cwd, which could match a real lane. Guard with `[ -n "$cwd" ]`.

NIT      Phase 12 Automated Verification  The criterion says "every phase 0-10 test file is in the diff" but passes at 9. Phases 0-10 name 13 test files.
         Enumerated: `awk '/^## Phase 0/,/^## Phase 11/' spec.md | grep -o 'tests/scripts/test_[a-z_]*\.py' | sort -u | wc -l` -> 13

Tree claims settled for the repaired sections:
- herdr-worktree: `bin_dir` is at line 54, `prompt`/`prompt_file` at 59-93, `main_checkout` at 150, `label` at 192, `ws` at 210, herdr-dev at 253, detach + watcher at 271. Header lines 31-47 hold the recovery description.
- herdr-worktree-watch: the recovery block is at lines 112-122, with the tuios focus step at 111.
- herdr-phase-change: `export PATH` is at line 24, and the final prompt is at line 94.
- hunk-review-pane: guard at 74-78 (the plan's "73-78" includes the comment line), `mkdir` at 81, header at 23.
- The `test_herdr_phase_change.py` setup uses `HOME=self.root` (line ~75). The `test_herdr_worktree_watch.py` tuios test is at line 263, and `recovery_lines` is at 50-55.
- `file_lock.LockTimeoutError(OSError)` exists and its message names the path.
- In pull_keep_index.py: `set_aside` at 195, `staged_clash_paths` at 261, `put_back` at 325, `--put-back` in `main` at 427-435. `test_the_re_apply_names_the_saved_commit_to_the_built_page_driver` is at line 309.
- The merge driver reads `BUILT_PAGE_STASH` and takes the stash's parent as its base (merge_built_page.py:310-330), which matches §1 step (5)'s choice of `%O`.

VERDICT: NEEDS CHANGES (2 blocker, 4 gap)
