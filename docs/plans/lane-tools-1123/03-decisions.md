# Design Decisions — lane-tools-1123

> Research: ./02-research.md
> Status: 23/23 resolved

## Queue

- [x] D1. Viewer cap kind: systemd-run hard cap or a portable RSS watchdog — from backend-architect
- [x] D2. What hunk-review-pane does after an OOM kill (exit 137) — from backend-architect
- [x] D3. Cap value owner and how lane-status finds live viewers — from backend-architect
- [x] D4. lane-status line and report key for an oversized viewer — from backend-architect
- [x] D5. Which hunk start paths get the cap — from backend-architect
- [x] D6. Where the merged check for an entry-less close lives — from backend-architect
- [x] D7. How a name or path maps to a workspace with no lane entry — from backend-architect
- [x] D8. Entry-less close sequence — from backend-architect
- [x] D9. Which git hooks run the link check — from backend-architect
- [x] D10. How the hook knows it runs in the stowed checkout; stow in CI — from backend-architect
- [x] D11. The ls probe: unit test, live snapshot check, or both — from backend-architect
- [x] Q1. Should an install script set core.hooksPath=.githooks — from backend-architect
- [x] G1. lane-status when the viewers read fails — from backend-architect
- [x] G2. systemd-run present but the scope fails to start — from backend-architect
- [x] G3. OOM restart on the outside-herdr path — from backend-architect
- [x] G4. Restart-window env knob — from backend-architect
- [x] U1. Repo CLAUDE.md edits — from backend-architect
- [x] R1. OOM signal the restart reads (plan review B1) — from plan-reviewer
- [x] R2. Post-merge test fixture folding (plan review B2) — from plan-reviewer
- [x] R3. One lane-status key per viewer (plan review G1; revises D4) — from plan-reviewer
- [x] R4. Matcher result assigned before the entry-less close (plan review G2) — from plan-reviewer
- [x] R5. Linked-worktree hook test pins the main-worktree gate (plan review G3) — from plan-reviewer
- [x] R6. Change files go through build_changes.py new (plan review G4) — from plan-reviewer

## Resolved

### 1. Viewer cap kind

- **Choice:** Run the viewer under `systemd-run --user --scope --quiet -p MemoryMax=1G -p MemorySwapMax=0` when Linux, systemd-run on PATH and `$XDG_RUNTIME_DIR/bus` are present; run it uncapped elsewhere, and lane-status names any viewer over the cap.
- **Reasoning:** Approved from the recommendation list by agent-evals-c3-owner (orchestrating session), 2026-11-23. The kernel enforces a hard cap with no polling loop; the repo already uses the same scope form in `lib/memory_cap_scope.py`.
- **Alternatives rejected:** A portable RSS watchdog: polls, lags a fast spike and adds a second process per pane to manage. A cap only on macOS-unsafe paths: none exists.
- **Trade-off accepted:** macOS and bus-less WSL run uncapped; only lane-status reports them.

### 2. After an OOM kill

- **Choice:** On exit 137, reset the tty (`stty sane`), print one line naming the kill and the cap, and restart the viewer; stop restarting and wait for Enter when the kill comes within 60 s of the start.
- **Reasoning:** Approved from the recommendation list by agent-evals-c3-owner (orchestrating session), 2026-11-23. A kill leaves the tty in raw mode; a huge diff would otherwise restart-thrash.
- **Alternatives rejected:** Exit on kill: the lane loses its diff pane until reopened. Restart forever: a diff larger than the cap loops at full CPU.
- **Trade-off accepted:** A viewer that dies fast twice needs a keypress to try again.

### 3. Cap value owner and viewer discovery

- **Choice:** `scripts/.local/lib/viewer-memory.bash` holds `HUNK_REVIEW_MEMORY_MAX` (default 1G, env override); `hunk-review-pane --viewers` prints JSON of live viewers from the per-pane state dirs (`hunk.pid`); per-process RSS comes from a new `lib/process_group.py` helper.
- **Reasoning:** Approved from the recommendation list by agent-evals-c3-owner (orchestrating session), 2026-11-23. The cap is a shared script default, so it lives in scripts/.local/lib; the state dir is hunk-review-pane's, so it lists its own viewers.
- **Alternatives rejected:** Hard-code 1G in both scripts: two copies drift. lane_status scanning /proc for `hunk diff`: a second grammar for viewer identity.
- **Trade-off accepted:** lane-status shells out to hunk-review-pane once per run.

### 4. lane-status report key

- **Choice:** One report key `viewers`: a list of viewers over the cap, each with pane id, pid and RSS; the line names each one.
- **Reasoning:** Approved from the recommendation list by agent-evals-c3-owner (orchestrating session), 2026-11-23. One key fits the existing report-dict and `--changes` diffing.
- **Alternatives rejected:** One key per viewer: floods `--changes` with churn as RSS moves.
- **Trade-off accepted:** Viewers under the cap do not show.

### 5. Which start paths get the cap

- **Choice:** Both the herdr loop path and the exec path start hunk under the cap.
- **Reasoning:** Approved from the recommendation list by agent-evals-c3-owner (orchestrating session), 2026-11-23. Both paths run the same unbounded viewer.
- **Alternatives rejected:** Cap only the herdr loop: tuios and plain-terminal viewers still grow without bound.
- **Trade-off accepted:** The exec path no longer replaces the shell process when capped; it runs systemd-run in its place.

### 6. Merged check for an entry-less close

- **Choice:** The merged check lives inline in herdr-lane-resume: fetch, then `git merge-base --is-ancestor <branch tip> origin/<default>`.
- **Reasoning:** Approved from the recommendation list by agent-evals-c3-owner (orchestrating session), 2026-11-23. herdr-worktree-prune is 991 lines and takes no new verb without a split.
- **Alternatives rejected:** A new prune verb: forces a split of a 991-line script for one check.
- **Trade-off accepted:** The check is a few lines next to, not shared with, prune's `check_merged`; a squash merge reads as unmerged and refuses.

### 7. Name or path to workspace with no lane entry

- **Choice:** Match the argument as a path exactly against `real_path(worktree.checkout_path)`, or as a name against the basename of a linked worktree's checkout path. Zero matches, several matches, the main checkout, or a name-only match under tuios: refuse with the candidates listed.
- **Reasoning:** Approved from the recommendation list by agent-evals-c3-owner (orchestrating session), 2026-11-23.
- **Alternatives rejected:** Match on workspace label: labels are free text and collide. Pick the first of several matches: closes the wrong lane.
- **Trade-off accepted:** A lane whose folder was renamed needs its path.

### 8. Entry-less close sequence

- **Choice:** Same sequence as an entry close minus the lane-file remove: refuse a working agent, refuse an unmerged branch before closing anything, close the workspace, wait for agents, run `herdr-worktree-prune --apply`.
- **Reasoning:** Approved from the recommendation list by agent-evals-c3-owner (orchestrating session), 2026-11-23. Prune keeps any tree with an open workspace, so the workspace closes first; the merged check runs first so a refusal leaves everything open.
- **Alternatives rejected:** Close first, check after: an unmerged lane loses its workspace.
- **Trade-off accepted:** None beyond D6's squash-merge refusal.

### 9. Which git hooks run the link check

- **Choice:** A `post-merge` hook in `.githooks` only. Pulls (pull.rebase=true) never fire it and stay out of scope.
- **Reasoning:** Approved from the recommendation list by agent-evals-c3-owner (orchestrating session), 2026-11-23. The orchestrator notes this machine sets core.hooksPath=.githooks, so the hook goes there.
- **Alternatives rejected:** post-rewrite or post-checkout as well: fires on every rebase and branch switch in every worktree.
- **Trade-off accepted:** A `git pull` that brings a new script still needs `install/check-script-links` by hand.

### 10. Stowed-checkout detection; stow in CI

- **Choice:** The hook acts only when its repo top-level is the main worktree and `~/.local/bin` links resolve into it; then it runs `install/check-script-links` and, on a gap, `stow -R -t "$HOME" scripts`. It always exits 0. CI installs stow.
- **Reasoning:** Approved from the recommendation list by agent-evals-c3-owner (orchestrating session), 2026-11-23. A linked worktree must never restow over the main checkout's links.
- **Alternatives rejected:** Restow from any worktree: points ~/.local/bin at a lane tree that gets deleted.
- **Trade-off accepted:** A machine whose links point elsewhere gets no restow, only silence.

### 11. ls probe

- **Choice:** A unit test only: `zsh -i` with a temp ZDOTDIR sourcing zsh/.zshrc; with CLAUDECODE=1 `whence -w ls` reports a command, with it unset an alias.
- **Reasoning:** Approved from the recommendation list by agent-evals-c3-owner (orchestrating session), 2026-11-23. The guard already works today; the test pins it.
- **Alternatives rejected:** A live shell-snapshot check: depends on this machine's ~/.claude state and fails in CI.
- **Trade-off accepted:** The test reads .zshrc, not a real Claude Code snapshot.

### Q1. Install script sets core.hooksPath

- **Choice:** Out of scope.
- **Reasoning:** Approved from the recommendation list by agent-evals-c3-owner (orchestrating session), 2026-11-23. This machine already sets core.hooksPath=.githooks.
- **Alternatives rejected:** Add it to install/: a new install step the ticket did not ask for.
- **Trade-off accepted:** A fresh machine runs no post-merge hook until hooksPath is set by hand.

### G1. lane-status when the viewers read fails

- **Choice:** Print one `viewers: cannot read (<reason>)` line; the other lines still print; exit 1.
- **Reasoning:** Ruled by agent-evals-c3-owner (orchestrating session), 2026-11-23, approving the recommendation. Matches the existing `memory: cannot read` line.
- **Alternatives rejected:** Exit 2: a failed secondary read hides every lane line.
- **Trade-off accepted:** A scheduler sees exit 1 plus a line, not exit 2.

### G2. Scope fails to start

- **Choice:** Loud failure: the pane shows systemd-run's error and no viewer starts. No probe, no uncapped fallback.
- **Reasoning:** Ruled by agent-evals-c3-owner (orchestrating session), 2026-11-23, approving the recommendation. Loud-failure rule; never seen on this machine.
- **Alternatives rejected:** A start-up probe with uncapped fallback: hides a broken cap and the viewer grows again.
- **Trade-off accepted:** A broken user manager costs the review pane until fixed.

### G3. OOM restart on the outside-herdr path

- **Choice:** Both start paths share `run_viewer`, so both restart after an OOM kill.
- **Reasoning:** Ruled by agent-evals-c3-owner (orchestrating session), 2026-11-23, approving the recommendation. D5 already removed the exec.
- **Alternatives rejected:** Restart on the herdr path only: two behaviors for one viewer.
- **Trade-off accepted:** None known.

### G4. Restart-window env knob

- **Choice:** `HUNK_REVIEW_RESTART_WINDOW_SECONDS` (default 60) in `viewer-memory.bash`, documented in the hunk-review-pane header.
- **Reasoning:** Ruled by agent-evals-c3-owner (orchestrating session), 2026-11-23, approving the recommendation. The late-kill restart is untestable without it short of a 60 s wait.
- **Alternatives rejected:** Fake the clock through SECONDS: bash-version dependent.
- **Trade-off accepted:** One more env variable.

### U1. Repo CLAUDE.md edits

- **Choice:** Skip both lines (`--close <name|path>` at CLAUDE.md:48, and a Setup line for `.githooks/post-merge`). The final report carries the exact proposed text for the user.
- **Reasoning:** No user yes on 2026-11-23; agent-evals-c3-owner puts it to the user in the morning. CLAUDE.md edits need the user's yes.
- **Alternatives rejected:** Edit now: breaks the rule that CLAUDE.md edits need the user's yes.
- **Trade-off accepted:** CLAUDE.md lags the new behavior until the user rules.

### R1. OOM signal the restart reads

- **Choice:** Start the viewer scope as `--unit=hunk-review-<pane>-<pid>-<n>`. Restart only when `systemctl --user show <unit>.scope -p Result` reads `Result=oom-kill`, or the exit is 137; then `systemctl --user reset-failed <unit>.scope`. A 143 with any other Result never restarts.
- **Reasoning:** Ruled by agent-evals-c3-owner (orchestrating session), 2026-11-23, on plan review round 1. The real `hunk` is a node wrapper; under the scope an OOM kill exits 143 (probe: exit=143, Result=oom-kill), so a 137 match never fires. A bare 143 is also a plain SIGTERM from a pane close or a user kill, and the viewer must stay dead then.
- **Alternatives rejected:** Restart on 143: restarts a viewer the user killed. Run the native binary directly: ties the pane to hunkdiff's install layout.
- **Trade-off accepted:** One `systemctl` call per viewer exit; a test stub for systemctl.

### R2. Post-merge test fixture folding

- **Choice:** setUp makes `home/.local/bin` a real folder holding a foreign file before stowing, and asserts per-file links before the merge.
- **Reasoning:** Ruled by agent-evals-c3-owner (orchestrating session), 2026-11-23, on plan review round 1. Stow on an empty home folds `home/.local` into one folder link, so the merge test passes with no hook.
- **Alternatives rejected:** None raised.
- **Trade-off accepted:** None known.

### R3. One lane-status key per viewer

- **Choice:** Revises D4: one report key per oversized viewer, `viewer:<pane>`; `--changes` prints no `working` line for a `viewer:` key that goes away.
- **Reasoning:** Ruled by agent-evals-c3-owner (orchestrating session), 2026-11-23, on plan review round 1. One joined key reprints every viewer line when any one changes, and prints `viewers: working` when the last one drops.
- **Alternatives rejected:** Keep one key and filter the `working` line: still reprints unchanged viewers.
- **Trade-off accepted:** A viewer whose size changes prints again.

### R4. Matcher result assigned before the entry-less close

- **Choice:** `close_target` assigns `match_workspace_name`'s output to a variable, then calls `entryless_close` with it; the path branch passes the entry's `.name` to `close_lane`.
- **Reasoning:** Ruled by agent-evals-c3-owner (orchestrating session), 2026-11-23, on plan review round 1. A command substitution as an argument skips errexit, so a matcher refusal printed a second, wrong refusal.
- **Alternatives rejected:** None raised.
- **Trade-off accepted:** None known.

### R5. Linked-worktree hook test pins the main-worktree gate

- **Choice:** The fixture commits `.githooks/post-merge` and `install/check-script-links`; the linked-worktree test points the bin links into that worktree, so only the main-worktree gate stops the restow.
- **Reasoning:** Ruled by agent-evals-c3-owner (orchestrating session), 2026-11-23, on plan review round 1. As planned, the test passed with the gate removed.
- **Alternatives rejected:** None raised.
- **Trade-off accepted:** None known.

### R6. Change files through build_changes.py new

- **Choice:** Each phase's change file is made with `python3 ~/agent-evals/bin/build_changes.py new` (lands in `docs/changes/notes/`), and the phase rebuilds the change pages so `build_changes.py --check` passes.
- **Reasoning:** Ruled by agent-evals-c3-owner (orchestrating session), 2026-11-23, on plan review round 1. The planned `docs/changes/<date>-*.md` paths sit outside `notes/`, and no step rebuilt the pages.
- **Alternatives rejected:** None raised.
- **Trade-off accepted:** None known.

### R7. Phase 0 review cap: go, comment asks rejected

- **Choice:** Commit Phase 0 at its review cap and run Phases 1-6. Reject both asks to restore the comments at `viewer-memory.bash:64` and `:73`; the comments stay. The branch-wide review at Verify covers the locale-guard edit made after the cap.
- **Reasoning:** Ruled by agent-evals-c3-owner (orchestrating session), 2026-11-24, under the user's standing rule of 2026-11-22 that the orchestrating session rules on a lane's review cap and its asks.
- **Alternatives rejected:** None raised.
- **Trade-off accepted:** The locale-guard edit stays unreviewed until Verify.

### R8. Branch review asks: shared keep verdict out, empty pidfile rule in

- **Choice:** Reject the ask to have `herdr-lane-resume` read a keep-or-remove verdict from `herdr-worktree-prune` in this lane; agent-evals-c3-owner queues it as its own item. Adopt the spec.md:151 row rule: a state dir counts only when its `hunk.pid` is not empty.
- **Reasoning:** Ruled by agent-evals-c3-owner (orchestrating session), 2026-11-24, under the user's standing rule of 2026-11-22 that the orchestrating session rules on a lane's asks.
- **Alternatives rejected:** Splitting `herdr-worktree-prune` (991 lines) in this lane to add `--check <path> --json`.
- **Trade-off accepted:** The two keep-rule copies stay until the queued item lands.

### R9. lane-status reads the caller's viewer cap

- **Choice:** Reject the ask to record each viewer's start cap in its state dir. `oversized_viewer` keeps comparing against `HUNK_REVIEW_MEMORY_MAX` from the `--viewers` caller's environment.
- **Reasoning:** Ruled by agent-evals-c3-owner (orchestrating session), 2026-11-24, under the user's standing rule of 2026-11-22 that the orchestrating session rules on a lane's asks. The cap is set once per machine.
- **Alternatives rejected:** A per-row `cap_bytes` read from `$dir/cap`.
- **Trade-off accepted:** A cap that differs per pane or shell can misreport a viewer.

## Direction & Constraints

- Item 4 (ls): the CLAUDECODE guard already works. Every shell snapshot after commit 261942676 (2026-11-22 16:08) lacks the ls alias; every one before holds it. Only the regression probe is new work.
- core.hooksPath=.githooks is relative and set in ~/dotfiles/.git/config; linked worktrees run their own .githooks. ~/.local/bin holds per-file links into ~/dotfiles. A hook in a linked worktree must never restow.
- git/.gitconfig sets pull.rebase=true, so a plain pull never fires post-merge.
- herdr-worktree-prune is 991 lines; a new verb there needs a split first.
- CI (.github/workflows/script-tests.yml) installs ripgrep and zsh, not stow.
- Dropped at triage (rule 3, one sighting with self-recovery): test-herdr-worktree-watch and test-plan-check-owner flaky-test items.
- Acceptance criteria (34, AC1–AC34) approved as drafted, and damage paths P1–P5 ruled by agent-evals-c3-owner (orchestrating session; criteria owner `session`), 2026-11-23:
  - P1: a plain `git pull` (pull.rebase=true) never fires the hook — out of scope (D9 stands).
  - P2: a fresh machine without core.hooksPath runs no post-merge hook — out of scope (Q1 stands).
  - P3: an entry-less close refuses a squash- or rebase-merged lane (D6 stands).
  - P4: closing a lane that has an entry keeps today's behavior; no new unmerged refusal.
  - P5: macOS and bus-less WSL viewers run uncapped and are only reported (D1 stands).
