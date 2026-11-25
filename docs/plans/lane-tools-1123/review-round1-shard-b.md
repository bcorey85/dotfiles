# Plan review round 1, shard B (Phases 3-6)

DUCK     Phase 3: splits `lane_entry`, adds a name/path dispatcher (`close_target`), a name-to-workspace matcher, an inline merged check and `entryless_close` in herdr-lane-resume, plus about 10 tests against stub herdr, a real git origin and the stubbed prune.
DUCK     Phase 4: adds `.githooks/post-merge` (gated to the main worktree whose bin links point into it; runs check, restow, recheck; always exits 0), adds stow to the CI apt line, and adds tests that run real git merges and real stow in a temp HOME.
DUCK     Phase 5: adds `tests/scripts/test_zshrc.py`, which runs `zsh -i -c 'whence -w ls'` with and without CLAUDECODE. I ran this probe and it gives `ls: alias` and `ls: command`, so the shape works.
DUCK     Phase 6: `/close-branch` review, then the full suite, `build_changes.py --check` and a propagation rg.

BLOCKER  Phase 4 §3 Tests setUp  The stow fixture folds `home/.local` into one directory symlink, so the main "merge adds a script, the link exists" tests pass with no hook at all.
         Evidence: setUp says "`home/.local/bin` stowed with `stow -R -t home scripts`", with no pre-made `home/.local/bin` and no `--no-folding`. I ran exactly that in a scratch home: `home/.local -> dotfiles/scripts/.local`. A `two` added afterwards appeared in `home/.local/bin/` at once, with no restow.
         Reading: on a fresh temp home, stow links the highest folder it can. So `test_a_merge_that_adds_a_script_links_it` and `test_a_fast_forward_merge_that_adds_a_script_links_it` pass even if the hook is deleted. This is the ticket's own Done-when test (AC3, AC27), and it cannot fail. `test_no_gap_runs_no_stow` also never sees a gap. The real `~/.local/bin` holds per-file links (Constraints), and the fixture never reproduces that. The plan has to say that setUp creates `home/.local/bin` as a real folder with a foreign file in it (or stows with `--no-folding`), and asserts per-file links before the merge.

GAP      Phase 3 §1 step 7 `close_target`  `entryless_close "$(match_workspace_name arg)"` does not stop under `set -e` when the matcher refuses.
         Evidence: plan step 7 says "without, `entryless_close "$(match_workspace_name arg)"`". The script runs `set -euo pipefail` (herdr-lane-resume:26). Its existing callers use the assignment form `entry=$(lane_entry "$name")` (:91, :153), which does propagate the exit.
         Reading: a command substitution used as an argument does not trigger errexit. When the matcher hits `fail`, only its subshell exits. `entryless_close ""` then runs and prints a second, wrong refusal. The plan should say to assign to a variable first.

GAP      Phase 4 §3 `test_a_merge_in_a_linked_worktree_restows_nothing`  This test passes with the main-worktree gate (D10, `in_main_worktree`) removed.
         Evidence: setUp names only `scripts/.local/bin/one` as committed; the hook is "copied". `core.hooksPath=.githooks` is relative, and each linked worktree runs its own `.githooks`. In this fixture, `~/.local/bin` links into the main checkout.
         Reading: if the hook is not committed, the linked worktree has no `.githooks/post-merge`, and git runs nothing. If it is committed, `bin_links_into` fails first anyway. Either way, gate 1 has no test that can fail. The plan should say the hook and `install/check-script-links` are committed. To pin gate 1 on its own, the linked worktree's scripts must be the ones bin links to.

GAP      Phase 3 §4 / Phase 4 §4 change files  The change-file paths are not where the change log reads notes, and no step rebuilds the pages that Phase 6's `--check` compares.
         Evidence: plan rows say `docs/changes/<date>-*.md`; build_changes.py reads `<root>/notes/<stem>.md` and `--check` compares built pages with a fresh build. `grep -n 'docs/changes/' spec.md` -> 4 (lines 220, 266, 327, 374; only 220 names `build_changes.py new`).
         Reading: a file at the stated path sits outside `notes/` and is silently ignored; a note made with `new` needs a page rebuild that no step schedules, so Phase 6 `--check` fails.

NIT      Phase 3 §1 step 7  `close_lane` takes a name, not an entry; say the path branch passes the entry's `.name`.

NIT      Shard vs spec.md  The shard is behind spec.md (AC30, AC32, AC4, AC6 owners added there). Judged against spec.md.

NIT      Phase 3 test for AC20  The prune is a stub, so "remove its worktree" shows only as a prune event; the AC mapping should say so.

Claims checked true: herdr-lane-resume functions and lines, orchestration.md:37, zsh/.zshrc:379-383, CI apt line, .githooks contents, check-script-links DOTFILES_DIR, lanes.py get --containing, herdr-worktree-prune 991 lines with check_merged at :560, test_no_entry_exits_1_and_prunes_nothing, unittest -k exit 5. Not settled: herdr-api `is_linked_worktree`.

VERDICT: NEEDS CHANGES (1 blocker, 3 gap)
