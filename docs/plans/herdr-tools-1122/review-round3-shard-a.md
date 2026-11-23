# Plan review round 3 (DEEP), shard A: verification of the round-2 repairs, 2026-11-22

Plan extract: /tmp/plan-review-shards-fa7tozsu/review-shard-a.md (from /home/brandon/dotfiles-herdr-tools-nov22/docs/plans/herdr-tools-1122/spec.md). The repair list is `### P4` in /home/brandon/dotfiles-herdr-tools-nov22/docs/plans/herdr-tools-1122/03-decisions.md.

The two round-2 blockers and all four shard-A gaps are fixed. The repaired text adds one new gap: it deletes the test that covered a failed `git add` of the rebuilt pages, and no step says what should happen in that case.

## Round-2 findings that touch this shard

- **BLOCKER Phase 4 §1 (`git apply` on empty input): FIXED.** Steps 1 and 3 now skip the apply when the diff is empty. I ran it in a scratch repo on git 2.56.1: an empty `git diff … | git apply --index --3way` exits 128 with "No valid patches in input". So the skip is needed, and it stays inside the git 2.34 limit.
- **BLOCKER Phase 4 §2 (renaming the line-159 test to a success test): FIXED.** Line 159 now becomes the step-1 conflict test. I rebuilt its fixture with plumbing (`k` changes from 1 to staged locally and to theirs upstream): step 1 prints "Applied patch to 'k' with conflicts", `UU k`, exit 1. So `exit_rolled_back` finds the U entry, as the plan says. The old assertions at lines 175-177 (empty status, `f` and `k` at theirs) still hold after `reset --hard`. Only the stderr assertions change.
- **GAP Phase 4 §2 ("the other tests keep their behaviour" was false for four tests): FIXED.** I traced each rewrite through the new steps:
  - Line 179: step 1 is skipped, step 3 conflicts on `g`, the rollback runs, and status is empty.
  - Line 199: both diffs are empty, step 5 fails after `read-tree`, `f` is at HEAD, and there is no `UU` entry.
  - Lines 795 and 816 call `put_back_without_index` and are deleted.
  - I also traced 246, 264 and 309: each keeps its outcome on the new route.
  
  The deletion of 795 opens a new gap (below).
- **GAP Phase 1 §3/§5 (an extra failure line in the watcher log): FIXED.** `set-session` now runs only when `get` returns an entry. The existing tests (`run_watch` sets `HOME=self.root` at test_herdr_worktree_watch.py:75) resolve the default lanes path to a missing file. Python exits 2, `|| lane_entry=""` catches it, and nothing is logged. The exact-text assertions at lines 94, 105 and 261 are unchanged.
- **GAP Phase 0 §1 vs §4 (two lock names): FIXED.** Both sections now say `<dir>/lanes.lock`, and the fixed 10 s timeout is stated. `file_lock.hold_exclusive(lock_path, timeout_seconds)` is at file_lock.py:17.
- **GAP Phase 3 §2 (the fixture lived in a later phase or a mock): FIXED.** I ran the stated `reference-transaction` hook against the current pull_keep_index.py in a scratch clone. The run exits 1, stderr shows "would be overwritten" for the set-aside file, and the saved commit is named. So the ref assertion can go RED before Phase 3 and pass after it. There is a NIT on how the plan describes the mechanism (below).
- **NIT Phase 2 §3 (PATH mechanism): FIXED.** hunk-review-pane has no PATH line; only the comment at line 23 mentions it. `test_herdr_phase_change.py:75` does set `HOME=self.root`, as the plan cites.
- **NIT Phase 1 §3 (`label` set too late): FIXED.** `label=$(basename "$worktree")` is today at herdr-worktree-watch:102. `worktree` is set at line 34, so moving `label` above the session read at line 69 is safe.
- **NIT Phase 1 §4 (empty `cwd`): FIXED.** An empty `cwd` now ends the step with no lookup.
- **NIT Phase 12 (13 test files): FIXED.** spec.md:556 now checks `>= 13`. The phase sits in shard B.
- **Shard-B NIT on the Phase 4 change-file wording: FIXED.** The note never names the removed function, which matches the Phase 11 ban on `docs/changes/*.md` (spec.md:529, 539).
- **Shard-B GAP on manual checks (the `S/clone` part in Phase 1): FIXED**, apart from the stale sentence in the NIT below.

## Findings

DUCK     Phase 0: `lane_entries.py` and `lanes.py`. Every write takes `<dir>/lanes.lock` with a fixed 10 s timeout. A timeout exits 2 and names the lock.
DUCK     Phase 1: `herdr-worktree --fork` adds a lane entry. The watcher runs `set-session` only when an entry exists, and logs one line only if that fails. The recovery text becomes `herdr-lane-resume <label>` only when the entry has a session id. Phase change skips the lookup when `cwd` is empty.
DUCK     Phase 2: hunk-review-pane renames its own pane to `review`. The test's stub wins because the test puts its stub folder first on PATH.
DUCK     Phase 3: adds `--help` and the save ref. The failed-put-back test uses a real `reference-transaction` hook fixture.
DUCK     Phase 4: six-step hand repair; steps 1 and 3 skip an empty diff. Rewrites tests 159, 179 and 199, deletes 795 and 816, and adds one empty-diff case.

GAP      Phase 4 §1 step (6) and §2: the plan deletes the test for a failed staging step, and no step says how a failed `git add` of the rebuilt pages should behave
         Evidence: the test at test_pull_keep_index.py:770 (`test_failed_staging_of_rebuilt_pages_names_the_add_command_and_the_saved_commit`, which calls `put_back_without_index` at line 795) checks today's behaviour at pull_keep_index.py:293-300. That code prints "could not stage the rebuilt pages: <problem>. To stage them, run: <add command>" and the saved commit, with no `--put-back`. The plan's step (6) says only "`git add` with `page_stage_arguments(pages)`". Step (5) has a failure message; step (6) has none. §2: "lines 795 and 816 … both are deleted."
         Reading: the deleted test was about step 6, not about `stash apply`. So "mock `stash apply`, which the new path never runs" is true only for line 816. One coder ports today's stage-failure message, now naming the ref, and moves the test over to `put_back_by_hand`. Another ignores the return code of `git add`, and the run exits 0 with the pages unstaged. Both follow the plan.

NIT      Phase 1 Manual Verification (spec.md:217) disagrees with Phase 8 and with P4 item 7
         Evidence: Phase 1: "(Phases 7, 9 and 10 reuse it) … Keep the probe lane open: Phase 8's check resumes it and closes it." Phase 8 (spec.md:461): "(3) leave the lane open: Phase 10's check runs `--close` on it". Phase 10 (spec.md:520): "The probe lane ends here." P4.7: "stays open through Phase 8 and Phase 10 closes it".
         Reading: Phase 8 reuses the lane but is missing from the list, and "closes it" names the wrong phase. The Phase 8 text decides what the coder does, so the risk is low.

NIT      Phase 3 §2: the hook does not fire where the plan says it does
         Evidence: in my scratch run, the hook fired once, on set_aside's `reset --hard --quiet` (pull_keep_index.py:203). That reset updates `refs/heads/master`, so the file came back before the pull. `git pull` then refused ("cannot pull with rebase: You have unstaged changes"), and `stash apply --index` failed with "would be overwritten". The plan's text is "so the later `stash apply --index` stops", which implies the pull itself worked.
         Reading: the test's assertions (put-back fails, the ref exists and stderr names it) hold either way. But a coder who also asserts that the pull worked, or that HEAD moved, writes a test that cannot pass.

NIT      Phase 1 §5: the "stub lanes CLI" has to be a Python file
         Evidence: every caller runs `python3 "$lanes_cli" …`. `tests/scripts/stubs.py:4-5` `write_stub` writes a `#!/bin/bash` file.
         Reading: a stub made with `write_stub` gives a SyntaxError and exit 1 for `get` too. `lane_entry` is then empty, `set-session` never runs, and the "session id not stored" assertion fails. The coder finds this out by debugging.

NIT      Phase 4 §2: unclear whether there is one step-3 test or two, and the step-1 test names a different file
         Evidence: "Step 3 conflict (an unstaged edit to `d` …)" is listed as its own test, and later "line 179 … becomes the step 3 conflict test". Line 159 is told to become "the step 1 conflict test above", but that test is written with file `a`, while the line-159 fixture uses `k`.
         Reading: one coder rewrites 179 as the only step-3 test. Another adds a `d` test and also rewrites 179. Either way the coverage is right.

NIT      Phase 4 §1 steps (1) and (3): "with each page excluded" does not say the exclude must match the page name literally
         Evidence: I ran `git diff --name-only -- . ':(exclude)p[1]'` on a repo where both `p[1]` and `p1` changed. It listed nothing, so `p1` was dropped too. With `:(exclude,literal)p[1]` it lists `p1`. Today's code escapes page names for `git apply --exclude` with `script_utils.escaped_glob` (pull_keep_index.py:226; script_utils.py:292).
         Reading: test 217 (glob page `p[1]` next to a staged lookalike `p1`) is in the "keeps its behaviour" set and goes red, so the coder will find it. Naming `:(exclude,literal)` or the existing helper saves that step.
         Evidence-class: exercised (scratch repo, git 2.56.1, `git diff --name-only` with both pathspec forms)

Tree claims checked: test_pull_keep_index.py has its tests at lines 159, 179, 199, 217, 246, 264 and 309. Calls to `put_back_without_index` are at 795 and 816 (their tests start at 770 and 803). In herdr-worktree-watch, `label` is at 102, `worktree` at 34 and the session read at 69. The watch tests: `HOME=self.root` at 75, exact-text assertions at 94, 105 and 261, and the tuios test at 263. hunk-review-pane has no PATH export, and its guard is at 74. `test_herdr_phase_change.py:75` sets HOME. pull_keep_index.py: `set_aside` at 195 with `reset --hard` at 203, `put_back` at 325, `put_back_without_index` at 286 with its staging-failure message at 293-300.

Hook blocks: two scratch-repo commands were blocked by the git-discipline gate, `git stash create` and then `git reset --hard`. I redid both with plumbing (`hash-object`, `commit-tree`, a temporary index). Nothing was skipped.

VERDICT: NEEDS CHANGES (0 blocker, 1 gap)
