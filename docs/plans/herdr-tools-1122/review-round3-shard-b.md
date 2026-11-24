# Plan review round 3 (DEEP), shard B: verification of the P4 repairs, 2026-11-22

DUCK     Phase 5: under the lock, `shared_pull` now fetches into `refs/pull-keep-index-fetch/<remote>/<branch>`, reads it, deletes it, then follows the same already-held, diverged, overlap and ff-only steps as before.
DUCK     Phase 6: resolve as before. Test rows now have live `sleep 600` pids, and the stub agent list carries `agent: "claude"`.
DUCK     Phase 7: marker as before. The no-sender test now uses a stub `session_pane.py` that branches on its first argument (resolve succeeds, sender fails). The manual check runs the worktree copy against the probe lane.
DUCK     Phase 8: the herdr-dev stub answers `{}` to every verb it does not shape. The manual check resumes the probe lane and leaves it open.
DUCK     Phase 9: the manual check runs `lane_status.py` from the worktree by its path.
DUCK     Phase 10: the manual check does a dry run that lists the probe as `open lane`, then `--close` against the real prune, then checks the worktree count fell by one, then deletes `S/clone`.
DUCK     Phase 12: the diff check counts at least 13 files under `tests/scripts/`.

## Prior findings (round 2, shard B)

- GAP, Phase 7 no-sender stub vs the Phase 6 resolve step: **PARTIAL.** The stub now answers `resolve` with `as-given`, exit 0, and `sender` with null name, exit 1, so the order problem is gone. But the new wording ("branches on `$1`") specifies a shell stub, and the script runs the stub through `python3`. See GAP 1 below.
- GAP, manual checks ran master's stowed copies, and Phase 10 had no probe lane to close: **FIXED.**
  - Phase 6 (shard :176), Phase 7 (:213), Phase 9 (:278) and Phase 10 (:308) all use `/home/brandon/dotfiles-herdr-tools-nov22/...` paths.
  - Phase 8 :249 leaves the lane open, and Phase 10 runs `--close` against the real prune, which is run from `$bin_dir`, so it is the worktree copy.
  - The "already merged" premise holds: a clone of this worktree sets `origin/HEAD` to the branch. Ran `git clone --no-checkout <worktree> c && git -C c symbolic-ref refs/remotes/origin/HEAD` -> `refs/remotes/origin/fix/herdr-tools-nov22`. The prune's `check_merged` (herdr-worktree-prune:518-519) compares against that, so a probe branch with no commits of its own reads as merged.
  - `check_lane_open` goes in after `check_default` (CHECKS at :610-611), which puts it ahead of `check_herdr`. So the dry run reports `open lane` even while the probe's agent is alive.
- NIT, Phase 12 `>= 9`: **FIXED.** The check now uses `>= 13`. I ran `awk '/^## Phase 0/,/^## Phase 11/' spec.md | grep -o 'tests/scripts/[a-z_]*\.py' | sort -u` -> 13 names.
  - One remaining weakness: `grep -c '^tests/scripts/'` also counts files under `tests/scripts/` that are not tests (`stubs.py`, `toolkit_paths.py`, fixtures). If any of those change, the check passes with a test file missing. `'^tests/scripts/test_'` would close that.
- NIT, the Phase 11 ban vs Phase 4's change-note wording: shard A's text (P4.8), so not verified here.
- NIT, Phase 5 FETCH_HEAD race: **FIXED.**
  - The fetch now uses an explicit `+<ref>:refs/pull-keep-index-fetch/<remote>/<branch>` and reads the ref with `rev-parse --verify` before deleting it.
  - The saved-ref listings use `for-each-ref ... refs/pull-keep-index/` with a trailing slash (spec.md:259). That pattern cannot match `refs/pull-keep-index-fetch/...`, so the plan's claim of no collision holds.
- NIT, Phase 6/7 rows need live pids and `agent: "claude"`: **FIXED.**
  - `live_session_rows` reads every `*.json` row file and keeps only rows whose pid is alive (session_registry.py:38-51). The row file name is not tied to the pid, so the Phase 6 and Phase 7 rows can share one `sleep 600` pid in two files.
  - The test runs with `HOME=self.root` (test_herdr_phase_change.py:75) and with no `CLAUDE_CONFIG_DIR` in the environment, so `sessions_dir()` is `self.root/.claude/sessions`.
- NIT, the herdr-dev stub list: **FIXED.** Every herdr-dev line number cited in Phase 8 §3 matches the tree:
  - `pane current` :51
  - `pane send-keys` :61, :68
  - `pane resize` :100, :136
  - `tab rename` / `pane rename` :108-109, :131
  - `tab create` :140
  - `tab focus` :145, :165
  - `pane focus` :166

  With `{}` from `tab create`, `c1` is the string `null`, and `split null` still gets the shaped `pane split` answer, so the script runs to the end under `set -e`.

## New findings

GAP      Phase 7 §2 (repaired sentence): the no-sender stub is described as shell, but herdr-phase-change runs it with `python3`.
         Evidence: Phase 6 §2: `resolved=$(python3 "$session_pane" resolve "$target") || exit 1`. Phase 7 §1: `sender_json=$(python3 "$session_pane" sender ...)`. Phase 7 §2: "a stub `session_pane.py` (through `HERDR_SESSION_PANE`) that branches on `$1`". The repo's stub helper writes bash: tests/scripts/stubs.py:4-5 `path.write_text("#!/bin/bash\n" + body + "\n")`. The plan's Approach also says "stub binaries through `tests/scripts/stubs.py write_stub`".
         Reading: a coder who follows "`$1`" and the repo's `write_stub` writes a bash `case "$1"` file. `python3` hits a SyntaxError on it, so `resolve` exits 1, herdr-phase-change leaves through `|| exit 1`, and stderr carries a Python traceback, not `(no session)`. The test fails for the wrong reason. The other reading is a Python stub that branches on `sys.argv[1]` and is written with `write_text`, not `write_stub`. Only that reading passes.

NIT      Phase 1 Manual Verification vs repaired Phase 8/10 Manual Verification: the lane's lifetime is described two ways.
         Evidence: Phase 1 (spec.md:217) says "Phases 7, 9 and 10 reuse it" and "Keep the probe lane open: Phase 8's check resumes it and closes it". Phase 8 (shard :249) says "leave the lane open: Phase 10's check runs `--close` on it". Phase 6's manual check also needs a live lane and is not in Phase 1's list.
         Reading: a coder who reads Phase 1 runs `--close` in Phase 8, and Phase 10's check then has no lane. Phase 1's sentence needs the P4.7 wording.

NIT      Phase 7 Manual Verification (repaired): the variable is set as a command prefix, then read as a shell variable.
         Evidence: shard :213 is `HERDR_LANES_CLI=... HERDR_SESSION_PANE=... /home/.../herdr-phase-change ...`, followed by "`python3 "$HERDR_LANES_CLI" get <name>`". A prefix assignment does not survive into the next command, and Bash tool calls do not keep shell state, so the second command runs `python3 ""`. Phase 10 (:308) says "with ... set", which reads as exported.
         Enumerated: `grep -n '"\$HERDR_LANES_CLI"' spec.md` -> 3 (217, 425, 520). Two of them (217, 425) use the prefix form.

NIT      Phase 10 Manual Verification (repaired): the claim that the probe "has no commits of its own" depends on what the probe lane does, and the plan never pins that down.
         Evidence: Phase 1's fork uses `--prompt-file <brief>` with no brief content specified. Phase 8 step 2 resumes the lane with that brief, so the agent acts on it again. `--close` step 2 refuses while the agent is `working`.
         Reading:
         - A brief that makes the agent edit or commit leaves the tree dirty or ahead of origin. The prune then keeps the tree, and "`n - 1`" fails for a reason that is not the code's fault.
         - Running `--close` while the agent is still on the brief exits 1.

         The fix is to state that the brief is a no-op (for example "reply ok and stop") and to wait for the agent to be idle before step 2.

NIT      Phase 5 §1 (repaired): the fetch ref is built from the remote's name, and some remote values make an invalid ref name.
         Evidence: `git check-ref-format refs/pull-keep-index-fetch/./main` -> exit 1. A URL remote also exits 1. `configured_remote` returns `branch.<b>.remote`, which may be `.` or a URL (pull_keep_index.py:351-353). On such a branch, the shared route's fetch fails with exit 1. The run is still safe: nothing has been set aside at that point.
         Second issue: when no target is given, the plan does not say whether `<branch>` is the current branch or the branch named by the merge ref. The two differ when the upstream has another name. Either choice works.

Claims settled against the tree:
- herdr-phase-change: `set -euo pipefail` at :23, `export PATH` at :24, the plain-prompt `pane current` at :58, `agent get` at :65, `agent prompt` at :78 and :94. The existing stub does not record the target of `agent get`, so Phase 6's "each call `agent get` ... with the stub pane id" needs the stub extended. That is unrepaired text and is not counted here.
- herdr-worktree-prune: 949 lines. `CHECKS` is at :610-611 and ends with `check_herdr`. `start_up` reads `origin/HEAD` at :628-631. `check_merged` is at :518, `check_process` at :581, `check_herdr` at :591.
- session_registry.py: `live_session_rows` at :38-51. `other_live_session_in` at :54. `session_display_name` at :79.
- `~/.local/bin/herdr-api`, `herdr-phase-change` and `herdr-worktree-prune` all link into `/home/brandon/dotfiles` (master). This confirms the manual checks need the worktree paths they now have.
- Not settled, because it is outside the tree: the shape of the tuios shim's `workspace list` (unchanged from round 2).

VERDICT: NEEDS CHANGES (0 blocker, 1 gap)
