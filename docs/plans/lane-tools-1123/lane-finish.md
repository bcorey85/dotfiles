# Lane finish steps (lane-tools-1123)

This session is the lane `dotfiles-lane-tools-nov23` on branch `fix/lane-tools-nov23`. It reports to `agent-evals-c3-owner` with SendMessage; every question for the user and the result go there, never to this pane. Read `~/.claude/skills/_shared/lane-brief.md` first.

After `/code docs/plans/lane-tools-1123/spec.md` finishes:

1. Run the full suite under `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh`, then `/verify-branch docs/plans/lane-tools-1123`.
2. Merge origin/master if it moved; commit and push the branch with a plain push (`python3 ~/.claude/scripts/tools/pull_keep_index.py <repo>` right before `git -C <repo> push -u origin HEAD`), never force.
3. Close each item: `python3 ~/agent-evals/bin/build_queue.py set <slug> --status done --outcome <change stem>` for
   - lane-diff-viewer-pane-grows-without-bound-and-eats
   - herdr-lane-resume-close-refuses-a-merged-lane-that
   - a-merge-that-adds-a-script-under-local-bin-leaves
   - ls-t-still-runs-eza-in-agent-shells-after-the
   The two triage drops (test-herdr-worktree-watch-the-120-second-wait-test, test-plan-check-owner-home-folder-test-fails-only) are set locally but not committed. Commit and push only those six agent-evals item files and their generated rows; the tree holds other sessions' QUEUE.md, queue/index.md and deleted items: never commit those.
4. Send agent-evals-c3-owner: head hash and suite count, the verify-branch result, items fixed and dropped, any manual smoke check, and the exact proposed CLAUDE.md text (U1) from spec.md "What We're NOT Doing".

Lane limits: never kill processes you did not start; do not touch mutation-tester, refactor or calibration files, or `claude/.claude/scripts/review`; no CLAUDE.md or settings.json edits.
