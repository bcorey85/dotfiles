# Lane tools: viewer memory cap, entry-less lane close, post-merge restow, ls probe

> Ticket: ./00-ticket.md (four ~/agent-evals queue items)
> Research: ./02-research.md (goal-blind, produced before design began)
> Decisions: ./03-decisions.md (the design-resolution ledger)
> Date: 2026-11-23

<!-- Source precedence: on anything concrete, THIS file wins over the ledger (which records why, not what). A disagreement between them is a spec bug — report it. -->

## Summary

Each lane's diff viewer starts under a systemd memory scope where the machine has one, restarts itself after an OOM kill, and lane-status names any live viewer over the cap. `herdr-lane-resume --close` takes a lane name or a worktree path and closes a merged lane that has no lane file entry. A new `.githooks/post-merge` restows the `scripts` package when a merge in the stowed checkout leaves a script unlinked. A zsh unit test pins the CLAUDECODE guard on the `ls` alias.

## Phase Status

- [x] Phase 0: Contracts — viewer-memory lib and the `--viewers` JSON shape, frozen at plan approval (risk: high)
- [x] Phase 1: Walking skeleton — viewer starts under the cap and restarts after an OOM kill (risk: low)
- [ ] Phase 2: lane-status names oversized viewers (risk: low)
- [ ] Phase 3: Entry-less lane close (risk: high)
- [ ] Phase 4: Post-merge restow (risk: low)
- [ ] Phase 5: ls probe (risk: low)
- [ ] Phase 6: Close pass — /close-branch parallel review, one fix, fix-diff gate, recap (risk: high)

## Decisions

1. Viewer cap kind — `systemd-run --user --scope --quiet -p MemoryMax=<cap> -p MemorySwapMax=0` when Linux, systemd-run on PATH and `$XDG_RUNTIME_DIR/bus`; uncapped elsewhere. Trade-off: macOS and bus-less WSL stay uncapped, only reported.
2. After an OOM kill — while capped, when the scope's `Result` reads `oom-kill` or the exit is 137 (R1): `stty sane`, leave the alternate screen, print one line, restart; a kill within the restart window waits for Enter (EOF returns hunk's status). A 143 with any other `Result` never restarts.
3. Cap owner — `scripts/.local/lib/viewer-memory.bash` (`HUNK_REVIEW_MEMORY_MAX`, default 1G); `hunk-review-pane --viewers` prints JSON; RSS through new `process_group` helpers.
4. lane-status key — one report key per oversized viewer, `viewer:<pane>` (R3, revises D4).
5. Start paths — both the herdr loop and the outside-herdr path run under the cap. Trade-off: the outside-herdr path is no longer an `exec`.
6. Merged check — inline in `herdr-lane-resume`, twin of prune's `check_merged`. Trade-off: a squash merge reads as unmerged and refuses.
7. Workspace match — path exactly, or name against the basename of a linked worktree's checkout path; zero, several, main checkout, or name-only under tuios refuse.
8. Entry-less close — same sequence as an entry close minus the lane-file remove; refuses an unmerged branch before closing anything.
9. Hooks — `.githooks/post-merge` only; pulls stay out of scope.
10. Hook gate — acts only in the main worktree whose `~/.local/bin` links resolve into it; `stow -R -t "$HOME" scripts`; always exit 0. CI installs stow.
11. ls probe — a unit test only.
Q1. Install script setting core.hooksPath — out of scope.
G1. Viewers read fails — one `viewers: cannot read (<reason>)` line, other lines print, exit 1.
G2. Scope fails to start — loud failure, no uncapped fallback.
G3. OOM restart covers both start paths.
G4. `HUNK_REVIEW_RESTART_WINDOW_SECONDS` (default 60) env knob.
U1. Repo CLAUDE.md edits are skipped; the final report carries the proposed text (see Phase 3 and Phase 4).

## Approaches Considered and Not Taken

- A portable RSS watchdog process per pane: polls, lags a fast spike, and adds a second process to manage.
- A new verb in `herdr-worktree-prune` for the merged check: forces a split of a 991-line script for one check.
- post-rewrite and post-checkout hooks besides post-merge: fire on every rebase and branch switch in every worktree.

## Constraints

- Everything works on WSL, Ubuntu, macOS and Arch. systemd-run is absent on macOS (`declared-only`); the viewer runs uncapped there.
- `core.hooksPath=.githooks` is relative and set in `~/dotfiles/.git/config`; each linked worktree runs its own `.githooks` (`exercised`). A hook in a linked worktree never restows.
- `git/.gitconfig` sets `pull.rebase=true`, so a plain pull never fires post-merge (`exercised`).
- `~/.local/bin` holds per-file relative links into `~/dotfiles` (`exercised`).
- `install/check-script-links` takes DOTFILES_DIR from its own path (`exercised`).
- `herdr-worktree-prune` is 991 lines: no new verb there.
- CI (`.github/workflows/script-tests.yml`) installs ripgrep and zsh, not stow (`exercised`).
- The `hunk` on PATH is a node wrapper (`hunkdiff/bin/hunk.cjs`, `spawnSync` then `process.exit`). An OOM kill inside a `systemd-run --scope` stops the scope (`DefaultOOMPolicy=stop`), the shell sees 143, and `systemctl --user show <unit>.scope -p Result --value` prints `oom-kill` until `systemctl --user reset-failed <unit>.scope`; a clean exit reads `success`. A bare child killed directly exits 137 (`exercised`: scratch node allocator under `-p MemoryMax=100M`, 2026-11-23).
- `herdr-api workspace list` returns `.result.workspaces[]` with `workspace_id`, `label`, `worktree.{checkout_path,is_linked_worktree,repo_root,repo_key}` (`exercised`).
- `lanes.py get --containing PATH` exists; `lanes.py get /path` exits 2 (`exercised`).
- The prune keeps any tree with a workspace open or an open lane, so the workspace closes before the prune runs (`exercised`).
- Per-pane viewer state dir: `${XDG_RUNTIME_DIR:-$HOME/.cache}/hunk-review-pane/<pane id>` holding `root`, `handoff` and `hunk.pid`; the extension writes `hunk.pid` (`exercised`). Two stale dirs (w53_p6, w5A_p2) hold dead pids today.
- `zsh/.zshrc:379-383` aliases `ls` to eza only when CLAUDECODE is unset (`exercised`). A `zsh -i` test needs `NO_MUX=1` and a no-op `keychain` stub.
- shellcheck is not installed on this machine.
- Lane limits: do not touch mutation-tester, refactor or calibration files, or `claude/.claude/scripts/review`. No CLAUDE.md edits (U1).
- Toolkit scripts follow `docs/toolkit-script-rules.md`; `process_group.pid_is_alive` is the only liveness check.

## External Contracts

- **systemd-run --user --scope** — invariant: `-p MemoryMax=` and `-p MemorySwapMax=0` cap the scope; the child's exit status passes through; a kill at the cap leaves the scope unit `failed` with `Result=oom-kill` (exit 143 through the node wrapper). Breaks if violated: the viewer runs uncapped or the restart never fires. `exercised` (scratch probe, 2026-11-23).
- **git post-merge hook** — invariant: fires after a successful `git merge` (including fast-forward), not after `git pull --rebase` or a conflicted merge finished by `git commit`; its exit status does not undo the merge. `declared-only` (git docs); Phase 4's tests run real git merges against it.
- **GNU stow `-R -t DIR pkg`** — invariant: restows `pkg` into DIR; a real file in the way is a conflict with non-zero exit. `declared-only`; Phase 4's tests run real stow.
- **herdr-api workspace list JSON** — invariant above under Constraints. Tests use a fake list of the same shape.
- **lane-status report / seen.json** — wide-blast internal: `--changes` diffs the report dict against `seen.json`; a new key missing from an old file reads as None.

## Approach

- **Viewer**: `viewer-memory.bash` owns the cap value, its grammar, the availability check and the prefix array. `hunk-review-pane` sources it, wraps both start paths in `run_viewer`, and adds `--viewers`.
- **lane-status**: calls `hunk-review-pane --viewers`, checks each pid through `process_group` (`pid_is_alive`, `program_name`, `resident_bytes`), and names viewers over `cap_bytes` by lane, one `viewer:<pane>` key each.
- **Close**: `close_target` tells a path (contains `/`) from a name; an entry routes to today's `close_lane`; no entry routes to `entryless_close`.
- **Hook**: a gate on main worktree plus bin links into it, then check, restow, recheck.
- **ls**: a `zsh -i` test against the tree's `.zshrc`.

## Dependencies

- No new packages. CI gains `stow` in its apt line.
- Internal: `tests/scripts/stubs.py`, `tests/scripts/toolkit_paths.py`, `lib/process_group.py`, `lib/lane_entries.py` `entry_containing`, `lib/script_utils.py` `run_or_raise`, `tools/lanes.py`.

## Implementation Plan

### Current State Analysis

`hunk-review-pane` runs `hunk diff --watch` with no cap: a loop under herdr (line ~97), an `exec` outside it (line ~77). lane-status reads no per-process memory. `herdr-lane-resume --close` fails "no lane named X" when the lane file has no entry. No post-merge hook exists; `.githooks/pre-commit` is the only hook. No test covers `.zshrc`.

### Desired End State

The four ticket Done-when checks pass as tests (Phase 1, 3, 4, 5) and lane-status names an oversized viewer (Phase 2).

### What We're NOT Doing

- Pulls and conflicted merges finished with `git commit` (D9).
- An install script that sets `core.hooksPath` (Q1).
- A cap on macOS or bus-less WSL, or on `hunk-review-popup`.
- A merged check on the entry path of `--close`.
- Any change to `herdr-worktree-prune`.
- The `cat`, `ll` and `lt` aliases.
- Repo `CLAUDE.md` edits (U1). Proposed text for the final report:
  - `CLAUDE.md:48` scripts line: `herdr-lane-resume (reopens a dead lane from its lane file; `--close <name|path>` closes a finished lane, with or without a lane file entry, and prunes its worktree)`.
  - Setup list: `- .githooks/post-merge - after a merge in the stowed checkout, restows `scripts` when `install/check-script-links` finds a gap (no-op in linked worktrees)`.

### Acceptance Criteria

- **Criteria file**: `docs/plans/lane-tools-1123/acceptance-criteria.md`

A test covers a criterion by its behavior, never by a marker: it asserts at the public boundary a user or caller reaches, never an internal function. **No mocks inside such a test.**

### Implementation Approach

Phases are vertical: each lands one ticket item with its tests and its change file. Phase 0 freezes the two contracts Phases 1 and 2 share.

## Phase 0: Contracts

### Overview

Freeze the viewer-memory lib and the `--viewers` JSON shape.

### Changes Required:

#### 1. viewer-memory lib

**File**: `scripts/.local/lib/viewer-memory.bash` (new, sourced)
**Changes**:
- `viewer_memory_max="${HUNK_REVIEW_MEMORY_MAX:-1G}"`, grammar `^[0-9]+[KMG]$` (base 1024).
- `viewer_restart_window_seconds="${HUNK_REVIEW_RESTART_WINDOW_SECONDS:-60}"`, grammar `^[0-9]+$`.
- `viewer_memory_checked`: on a bad value returns 1 and prints `hunk-review-pane: HUNK_REVIEW_MEMORY_MAX=<v>: expected digits then K, M or G` (and the matching line for the window variable) to stderr.
- `viewer_memory_max_bytes`: prints the cap in bytes.
- `memory_cap_available`: `uname -s` is `Linux`, `command -v systemd-run`, `command -v systemctl`, and `-e "${XDG_RUNTIME_DIR:-}/bus"`. A comment names `claude/.claude/scripts/lib/memory_cap_scope.py cap_available` as the twin; that file gets the reverse comment.
- `set_viewer_cap_prefix <unit>`: sets array `viewer_cap_prefix=(systemd-run --user --scope --quiet "--unit=<unit>" -p "MemoryMax=$viewer_memory_max" -p MemorySwapMax=0)`, or `()` when the cap is not available.
- `viewer_scope_was_oom_killed <unit>`: returns 0 when `systemctl --user show "<unit>.scope" -p Result --value` prints `oom-kill`, else 1; always runs `systemctl --user reset-failed "<unit>.scope"` after the read, its errors sent to /dev/null (R1).

**File**: `claude/.claude/scripts/lib/memory_cap_scope.py` — one comment line naming the bash twin.

#### 2. `--viewers` JSON shape (documented in the lib header)

```json
{"cap_bytes": 1073741824,
 "viewers": [{"pane": "w5M_p2", "root": "/home/brandon/dotfiles-lane-tools-nov23", "pid": 936851}]}
```

One row per state dir holding `hunk.pid`; `root` is the `root` file's content or `""`. Rows are raw: liveness and identity are the reader's job. No state root: `{"cap_bytes": N, "viewers": []}`, exit 0. A pidfile that is not all digits: exit 2, stderr `hunk-review-pane: <file>: expected a pid`. A bad cap value: exit 2.

#### 3. Tests

**File**: `tests/scripts/test_viewer_memory.py` (new) — sources the lib in bash:
- `test_default_cap_is_1g_in_bytes` (1073741824).
- `test_cap_suffixes_k_m_g` (`512M` → 536870912).
- `test_bad_cap_value_is_refused_naming_the_variable`.
- `test_bad_restart_window_is_refused`.
- `test_prefix_is_empty_without_a_user_bus` and `test_prefix_is_the_systemd_run_scope_with_a_bus` (stub `uname`, `systemd-run`, `systemctl`, temp `XDG_RUNTIME_DIR`; the prefix carries `--unit=<unit>`).
- `test_an_oom_kill_result_reads_as_killed` and `test_a_success_result_reads_as_not_killed` (stub `systemctl` prints the Result from a file and logs `reset-failed`; both reset the unit).

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: the lib tests pass — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 python3 tests/parallel_tests.py test_viewer_memory.py`
- [ ] **Lint-verified**: `bash tests/lint.sh tests/scripts/test_viewer_memory.py claude/.claude/scripts/lib/memory_cap_scope.py`

#### Manual Verification:

- N/A (contract-only; Phase 1 exercises it end to end)

---

## Phase 1: Walking skeleton — viewer cap and restart

### Overview

`hunk-review-pane` starts hunk under the cap on both paths, restarts after an OOM kill, and lists viewers.

### Changes Required:

#### 1. Launcher

**File**: `scripts/.local/bin/hunk-review-pane`
**Changes**:
1. Source `../lib/viewer-memory.bash` beside `handoff-command.bash` (`:30-32`), same `readlink -f` form.
2. `state_root()` echoes `${XDG_RUNTIME_DIR:-$HOME/.cache}/hunk-review-pane`; `state_dir` uses it.
3. `--viewers` branch after `--state-dir`: `viewer_memory_checked || exit 2`; loop `"$(state_root)"/*/hunk.pid` (skip the unexpanded glob with `[ -f ]`); check the pid grammar; build the JSON with `jq` (one `jq -s` over rows), never string-built.
4. Before either start path: `viewer_memory_checked || exit 2`, then `set_viewer_cap_prefix`.
5. `run_viewer`: each start names a fresh unit `hunk-review-<pane or "term">-$$-<n>` (`n` counts starts), calls `set_viewer_cap_prefix "$unit"`, and runs `${viewer_cap_prefix[@]+"${viewer_cap_prefix[@]}"} hunk diff [base] --watch [untracked flag] "$@"`. With a non-empty prefix, the viewer was OOM-killed when `viewer_scope_was_oom_killed "$unit"` returns 0 or the status is 137 (R1); a 143 or any other status with a non-`oom-kill` Result returns hunk's status, no restart. On a kill: `stty sane 2>/dev/null || :`, `printf '\033[?1049l'`, print `hunk-review-pane: the viewer passed its <cap> memory cap and was killed; restarting`. If the kill came less than `viewer_restart_window_seconds` after the start (`$SECONDS`), print `hunk-review-pane: killed within <W> s of its start; press Enter to try again` and `read -r`; EOF returns hunk's status. With an empty prefix, return hunk's status unchanged (137 included).
6. `:77` becomes `run_viewer "$@"; exit $?` (the `exec` goes). `:97` becomes `run_viewer "$@"` then `hunk_status=$?`.
7. Header: the cap, the restart, `--viewers`, and the two env variables.

#### 2. Docs

**File**: `.claude/rules/hunk.md` — one sentence on the cap, the restart and `--viewers`.

#### 3. Tests

**File**: `tests/scripts/test_hunk_review_pane.py` — keep the existing class; add:
- `HunkReviewPaneCapTest` (stub `systemd-run` logs `"$*"` then `shift 8; exec "$@"`; stub `systemctl` prints the next Result from a counter file for `show` (default `success`) and logs each `reset-failed`; stub `uname` echoes `Linux`; `XDG_RUNTIME_DIR` with a `bus` file; stub `hunk` logs args and takes exit codes from a counter file):
  - `test_launcher_starts_hunk_under_the_memory_cap` — outside herdr and with `HERDR_PANE_ID`; the systemd-run log line matches `--user --scope --quiet --unit=hunk-review-\S+ -p MemoryMax=1G -p MemorySwapMax=0 hunk diff --watch`.
  - `test_an_oom_kill_result_restarts_the_viewer` (window 0; hunk exits 143 then 0; Result `oom-kill` then `success`; two runs, exit 0, output names the cap, the unit was reset).
  - `test_exit_143_with_a_success_result_does_not_restart` (hunk exits 143, Result `success`; one run, exit 143, no restart line).
  - `test_memory_max_variable_sets_the_cap` (`512M`).
  - `test_bad_memory_max_exits_2_before_hunk_starts`.
  - `test_no_user_bus_runs_hunk_uncapped`.
  - `test_not_linux_runs_hunk_uncapped` (uname prints `Darwin`).
  - `test_oom_kill_after_the_window_restarts_the_viewer` (window 0; 137 then 0; two runs, exit 0, output names the cap).
  - `test_oom_kill_inside_the_window_waits_for_enter` (stdin `"\n"`; prompt text, two runs, exit 0).
  - `test_oom_kill_inside_the_window_with_no_input_stops` (empty stdin; one run, exit 137, and stderr's assertions ignore any `stty` line).
  - `test_uncapped_exit_137_is_not_restarted`.
  - `test_a_scope_that_fails_to_start_starts_no_uncapped_viewer` (stub systemd-run exits 1 without running its command; hunk never runs, the exit is non-zero, and stderr shows systemd-run's error).
- `HunkReviewPaneViewersTest`:
  - `test_viewers_lists_each_state_dir_with_a_pid_file`.
  - `test_viewers_with_no_state_root_prints_an_empty_list`.
  - `test_viewers_reports_the_cap_in_bytes` (`2G` → 2147483648).
  - `test_a_pid_file_that_is_not_a_pid_exits_2_naming_it`.

#### 4. Change file

**File**: `docs/changes/notes/<date>-<slug>.md` — `python3 ~/agent-evals/bin/build_changes.py new --by claude-opus-5-5/main "the lane diff viewer starts under a memory cap and restarts after an OOM kill"`, fill the note, then `python3 ~/agent-evals/bin/build_changes.py` to rebuild the pages (R6).

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: launcher, restart and viewers tests pass — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 python3 tests/parallel_tests.py test_hunk_review_pane.py`
- [ ] **Test-verified**: the new tests run and pass — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 python3 -m unittest discover -s tests/scripts -p test_hunk_review_pane.py -k test_launcher_starts_hunk_under_the_memory_cap -k test_oom_kill_after_the_window_restarts_the_viewer -k test_an_oom_kill_result_restarts_the_viewer -k test_exit_143_with_a_success_result_does_not_restart -k test_viewers_lists_each_state_dir_with_a_pid_file`
- [ ] **Lint-verified**: `bash tests/lint.sh tests/scripts/test_hunk_review_pane.py`
- [ ] **Agent-run**: `scripts/.local/bin/hunk-review-pane --viewers | jq '.cap_bytes, (.viewers | length)'` prints `1073741824`, then the count of `"$XDG_RUNTIME_DIR"/hunk-review-pane/*/hunk.pid` files.

#### Manual Verification:

- [ ] **Manual-verified**: reopen a lane pane on this branch; `cat /proc/<pid from hunk.pid>/cgroup` names a `run-p*.scope`, and `systemctl --user show -p MemoryMax <scope>` prints `MemoryMax=1073741824`.

---

## Phase 2: lane-status names oversized viewers

### Overview

lane-status gains the `viewers` key and line.

### Changes Required:

#### 1. Process helpers

**File**: `claude/.claude/scripts/lib/process_group.py`
**Changes**: factor the `ps` call out of `command_line` into `_ps_field(pid, field)` (stripped stdout; `""` for a gone pid, exit 1 with empty stderr; raises `ProcessQueryError` otherwise). `command_line` keeps `-ww`. Add `resident_bytes(pid)` (`rss=`; `""` → `None`; digits → `int(kb) * 1024`; else raise) and `program_name(pid)` (`os.path.basename` of `comm=`, or `""`). Update the docstring.

**File**: `tests/scripts/test_process_group.py` — `test_resident_bytes_of_a_running_process_is_positive_and_none_when_gone`, `test_program_name_is_the_base_name_of_the_program`, `test_resident_bytes_raises_when_ps_fails` (stub `ps` on PATH). Existing tests stay green.

#### 2. lane-status

**File**: `claude/.claude/scripts/tools/lane_status.py`
**Changes**:
1. `VIEWER_PROGRAM = "hunk"`.
2. `read_viewers()`: `shutil.which("hunk-review-pane")` (`None` → `ViewerReadError("hunk-review-pane is not on PATH")`); `script_utils.run_or_raise([path, "--viewers"], ViewerReadError, check=True)`; `json.loads`; validate `cap_bytes` int and `viewers` a list of dicts with str `pane`, str `root`, int `pid`, else `ViewerReadError`.
3. `viewer_lines()`: `["viewers: cannot read (<msg>)"]` on `ViewerReadError` or `ProcessQueryError` (G1). Skip a row whose pid is not alive (`process_group.pid_is_alive`), whose `program_name` is not `hunk`, or whose `resident_bytes` is `None` or at or under the cap. Name each remaining viewer by `lane_entries.entry_containing(root)["name"]`, else `root`, else `pane`. Line: `viewer <name>: <size>, over <cap size> cap (pane <pane>, pid <pid>)`, where `size_text(bytes)` prints `N.N GB` at or over 1 GiB, `N.N MB` at or over 1 MiB, else `N KB`.
4. `current_report`: before the `if not lanes: return report` early exit, set `report[f"viewer:{pane}"] = line` for each oversized viewer, or `report["viewers"] = "viewers: cannot read (<msg>)"` on a read failure (R3). `changed_lines` prints no `<key>: working` line for a key that starts with `viewer` and goes to `None`; a key absent from `current` already prints nothing.
5. Docstring: the two line kinds and `HUNK_REVIEW_MEMORY_MAX`.

**File**: `tests/scripts/test_lane_status.py` — `stub_viewers(json_text, exit_code=0)` writes `bin_dir/hunk-review-pane`; `setUp` stubs an empty list; `live_hunk()` copies `sleep` to `root/prog/hunk`, starts it with cleanup, returns the pid. Tests: `test_a_viewer_over_the_cap_is_named_with_its_lane` (exit 1), `test_a_viewer_under_the_cap_prints_nothing`, `test_a_viewer_outside_any_lane_is_named_by_its_root`, `test_a_stale_pid_file_is_not_a_viewer`, `test_a_pid_held_by_another_program_is_not_a_viewer`, `test_a_failed_viewers_call_prints_cannot_read`, `test_viewer_json_with_a_bad_shape_prints_cannot_read`, `test_no_lanes_still_reports_an_oversized_viewer`, `test_changes_prints_a_viewer_line_once`, `test_changes_prints_only_the_viewer_whose_size_changed` (two viewers, one grows), `test_changes_prints_no_working_line_when_a_viewer_drops`, `test_a_small_cap_prints_in_kb`.

#### 3. Change file

**File**: `docs/changes/notes/<date>-<slug>.md` — `python3 ~/agent-evals/bin/build_changes.py new --by claude-opus-5-5/main "lane-status names a diff viewer over its memory cap"`, fill the note, then `python3 ~/agent-evals/bin/build_changes.py` to rebuild the pages (R6).

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: process and lane-status tests pass — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 python3 tests/parallel_tests.py test_process_group.py test_lane_status.py`
- [ ] **Test-verified**: the new tests run and pass — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 python3 -m unittest discover -s tests/scripts -p test_lane_status.py -k test_a_viewer_over_the_cap_is_named_with_its_lane -k test_a_failed_viewers_call_prints_cannot_read`
- [ ] **Lint-verified**: `bash tests/lint.sh claude/.claude/scripts/tools/lane_status.py claude/.claude/scripts/lib/process_group.py tests/scripts/test_lane_status.py tests/scripts/test_process_group.py`
- [ ] **Agent-run**: `HUNK_REVIEW_MEMORY_MAX=1K PATH="$PWD/scripts/.local/bin:$PATH" python3 claude/.claude/scripts/tools/lane_status.py` prints the plain run's lines plus one `viewer …` line per live viewer; neither `w53_p6` nor `w5A_p2` appears.

#### Manual Verification:

- N/A (the Agent-run check reads the live machine)

---

## Phase 3: Entry-less lane close

### Overview

`herdr-lane-resume --close <name|path>` closes a merged lane with no lane file entry.

### Changes Required:

#### 1. herdr-lane-resume

**File**: `scripts/.local/bin/herdr-lane-resume`
**Changes**:
1. Split `lane_entry` into `find_entry <name>` (entry JSON or nothing) and `lane_entry` (fails "no lane named"). Add `known_lanes`, shared by both failure messages.
2. `workspace_rows`: one `herdr-api workspace list`, printing `id\x1flabel\x1fcheckout\x1flinked` (`(.worktree.is_linked_worktree // false | tostring)`). `workspaces_on` reads it, matching unchanged.
3. `match_workspace_name <name>`: under `TUIOS_SOCKET` refuse; else collect `real_path(checkout)` of rows whose basename equals the name. One linked match prints it; zero linked with a non-linked match refuses "main checkout"; zero of either refuses "no lane named …"; several linked refuse and list them.
4. `branch_is_merged <wt> <main>`: comment `# Twin of herdr-worktree-prune check_merged (D6): fetch origin/<default>, then is-ancestor.` Refuse with a reason on: no `refs/remotes/origin/HEAD`, fetch failure, detached HEAD, the default branch itself, `merge-base --is-ancestor` exit 1 (`branch <b> is not merged into origin/<d> (a squash or rebase merge reads as unmerged); nothing changed`), any other exit (`could not check …`).
5. `checked_close_wait`: the `HERDR_LANE_CLOSE_WAIT` validation, called first by `close_lane` and `entryless_close`.
6. `entryless_close <wt>`: refuse a non-folder (`no lane file entry and no folder at <path>`) and a non-linked worktree (`<path> is not a linked worktree`, git-dir equals common-dir or not a repo); main checkout is the parent of `--git-common-dir`; `workspaces_on "$wt" "$(basename "$wt")"` empty refuses `no herdr workspace is open on <path>`; working-agent refusal (same awk line as `close_lane`); `branch_is_merged`; close each workspace; `wait_for_agents_to_leave`; `herdr-worktree-prune --apply` in the main checkout; return its status.
7. `close_target <arg>`: an argument containing `/` is a path — `lanes.py get --containing`; an entry whose `real_path(.worktree)` equals it passes the entry's `.name` to `close_lane` (unchanged signature); else `entryless_close`. A name with an entry goes to `close_lane`; without, `worktree=$(match_workspace_name "$arg")` on its own line, then `entryless_close "$worktree"` (R4: an assignment keeps errexit).
8. Case statement: `--close` → `close_target "$2"`, message `--close needs one lane name or worktree path`. Header: usage and an entry-less paragraph.

Every refusal exits 1, prints `herdr-lane-resume: <msg>` to stderr, and changes nothing.

#### 2. Docs

**File**: `claude/.claude/orchestration.md` — line 37: `--close <name>` becomes `--close <name|path>`, closing a merged lane with or without a lane file entry. No opencode port exists (sweep records it).

#### 3. Tests

**File**: `tests/scripts/test_herdr_lane_resume.py` — `EntrylessCloseTest(HerdrLaneResumeTest)` with a real bare origin, a main checkout (`git init -b master`, commit, push, `remote set-head origin master`), `worktree add root/<NAME> -b fork`, `GIT_CONFIG_GLOBAL=/dev/null` and identity env; `merge_fork()`; `workspace_on(path, linked=True)`. Tests:
- `test_entryless_close_by_name_closes_the_merged_workspace_and_prunes` (empty lane file, fake workspace list; events `herdr workspace close wX` then the prune; exit 0).
- `test_entryless_close_by_path_closes_the_merged_workspace_and_prunes`.
- `test_entryless_close_of_an_unmerged_branch_refuses_before_closing`.
- `test_entryless_close_refuses_a_working_agent`.
- `test_entryless_close_refuses_the_main_checkout` (by name and by path).
- `test_entryless_close_with_two_matching_workspaces_lists_both`.
- `test_entryless_close_by_name_under_tuios_refuses`.
- `test_entryless_close_by_path_with_no_workspace_refuses`.
- `test_entryless_close_of_a_detached_head_refuses`.
- `test_close_by_path_with_an_entry_uses_the_entry`.
- The existing `test_no_entry_exits_1_and_prunes_nothing` stays green unchanged.

#### 4. Change file

**File**: `docs/changes/notes/<date>-<slug>.md` — `python3 ~/agent-evals/bin/build_changes.py new --by claude-opus-5-5/main "herdr-lane-resume --close closes a merged lane that has no lane file entry"`, fill the note, then `python3 ~/agent-evals/bin/build_changes.py` to rebuild the pages (R6).

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: entry-less close tests pass — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 python3 tests/parallel_tests.py test_herdr_lane_resume.py`
- [ ] **Test-verified**: the new tests run and pass — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 python3 -m unittest discover -s tests/scripts -p test_herdr_lane_resume.py -k test_entryless_close_by_name_closes_the_merged_workspace_and_prunes -k test_entryless_close_of_an_unmerged_branch_refuses_before_closing`
- [ ] **Lint-verified**: `bash tests/lint.sh tests/scripts/test_herdr_lane_resume.py`

#### Manual Verification:

- [ ] **Manual-verified**: `scripts/.local/bin/herdr-lane-resume --close no-such-lane-xyz` exits 1 with `no lane named no-such-lane-xyz` and closes nothing.

---

## Phase 4: Post-merge restow

### Overview

A merge in the stowed checkout links any new script.

### Changes Required:

#### 1. Hook

**File**: `.githooks/post-merge` (new, mode 0755)
**Changes**: `#!/usr/bin/env bash`, `set -uo pipefail`, no `-e`; every path ends `exit 0`. Header names the two gates and "never fails the merge". Functions `in_main_worktree` (`--git-dir` equals `--git-common-dir`), `bin_links_into <top>` (some `$top/scripts/.local/bin/<name>` satisfies `[ "$HOME/.local/bin/<name>" -ef <script> ]`), `restow_scripts <top>`. When both gates hold: run `"$top/install/check-script-links"` (output discarded on a pass); on a gap, `(cd "$top" && "$STOW" -R -t "$HOME" scripts)`, then rerun the check and print its result. Stow failure prints `post-merge: stow -R scripts failed:` plus stow's stderr. Stow missing prints `post-merge: stow is not installed; links for new scripts are missing (run install/stow)`. `STOW` env override, default `stow`.

#### 2. CI

**File**: `.github/workflows/script-tests.yml` — apt line becomes `ripgrep zsh stow`; step name updated.

#### 3. Tests

**File**: `tests/scripts/test_post_merge_hook.py` (new) — `HOOK` from env `POST_MERGE_HOOK`, default `REPO_ROOT/.githooks/post-merge`; `skipUnless(shutil.which("stow"))`. `setUp`: temp `home`, `home/dotfiles` (`git init -b master`), `install/check-script-links`, the hook and `scripts/.local/bin/one` copied in and committed, `core.hooksPath .githooks`; `home/.local/bin` made as a real folder holding a foreign file `foreign`, then `stow -R -t home scripts` from `home/dotfiles`; setUp asserts `home/.local/bin` is not a symlink and `home/.local/bin/one` is (R2); env `HOME`, `GIT_CONFIG_GLOBAL=/dev/null`, identity, `PATH`. Tests:
- `test_a_merge_that_adds_a_script_links_it` (`git merge --no-ff`; `home/.local/bin/two` is the same file as the repo script).
- `test_a_fast_forward_merge_that_adds_a_script_links_it`.
- `test_a_merge_in_a_linked_worktree_restows_nothing` (R5: a linked worktree `home/lane` of `home/dotfiles`; `home/.local/bin` restowed from `home/lane` so its links point into the linked worktree; a merge there that adds `two` leaves `home/.local/bin/two` absent and the `STOW` log empty — only the main-worktree gate stops it).
- `test_a_checkout_that_bin_does_not_link_to_restows_nothing`.
- `test_a_stow_conflict_is_reported_and_the_hook_exits_0`.
- `test_no_gap_runs_no_stow` (a `STOW` stub log stays empty).
- `test_missing_stow_is_reported_and_the_hook_exits_0` (`STOW` names a missing program; the merge exits 0 and the output names stow as not installed).
- `test_ci_workflow_installs_stow` (reads `.github/workflows/script-tests.yml`; its apt install line names `stow`).

#### 4. Change file

**File**: `docs/changes/notes/<date>-<slug>.md` — `python3 ~/agent-evals/bin/build_changes.py new --by claude-opus-5-5/main "a merge that adds a script links it from ~/.local/bin"`, fill the note, then `python3 ~/agent-evals/bin/build_changes.py` to rebuild the pages (R6).

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: hook tests pass — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 python3 tests/parallel_tests.py test_post_merge_hook.py`
- [ ] **Lint-verified**: `bash tests/lint.sh tests/scripts/test_post_merge_hook.py`
- [ ] **Test-verified**: the hook is executable — `test -x .githooks/post-merge`

#### Manual Verification:

- N/A (the tests run real git merges and real stow)

---

## Phase 5: ls probe

### Overview

Pin the CLAUDECODE guard on the `ls` alias.

### Changes Required:

#### 1. Test

**File**: `tests/scripts/test_zshrc.py` (new) — `ZSHRC` from env `ZSHRC_FILE`, default the tree's `zsh/.zshrc`; `skipUnless(shutil.which("zsh"))`. `setUp`: temp `home`, `zdotdir/.zshrc` symlinked to `ZSHRC`, a stub dir with a no-op `keychain`, env from scratch (`HOME`, `ZDOTDIR`, `PATH=stub:`+system PATH, `NO_MUX=1`, `TERM=dumb`, `XDG_RUNTIME_DIR=home/run`). `whence_ls(**extra)` runs `zsh -i -c 'whence -w ls'` with `stdin=DEVNULL`, `timeout=60`, returns the last stdout line. Tests:
- `test_claude_code_shell_resolves_ls_to_the_command` (`CLAUDECODE=1` → `ls: command`).
- `test_interactive_shell_without_claudecode_aliases_ls` (→ `ls: alias`).

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: the ls probe passes — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 python3 tests/parallel_tests.py test_zshrc.py`
- [ ] **Lint-verified**: `bash tests/lint.sh tests/scripts/test_zshrc.py`
- [ ] **Agent-run**: in a Claude Code Bash call, `type ls` prints a path to the system ls (`ls is /usr/bin/ls`), not an alias or function.

#### Manual Verification:

- N/A (the Agent-run probe runs in a real Claude Code shell)

---

## Phase 6: Close pass

### Overview

`/close-branch`: scripts first, then four report-only reviewers in parallel on the whole branch diff, one coder that fixes every finding, a report-only gate on the fix diff, then the recap.

### Changes Required:

N/A — `/code` runs `/close-branch`.

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: full suite green — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh`
- [ ] **Test-verified**: change files valid — `python3 /home/brandon/agent-evals/bin/build_changes.py --check`
- [ ] **Agent-run**: nothing deleted — `git diff --diff-filter=D --name-only <base-sha>..<head-sha>` prints nothing.
- [ ] **Agent-run**: propagation sweep — `rg --hidden -n 'herdr-lane-resume --close|lane-status|hunk-review-pane' claude opencode .claude` shows every mention matching the new contracts; any skipped opencode port is stated.
- [ ] **Agent-run**: every reviewer finding fixed, shown wrong, or put to the orchestrator; the fix-diff gate passed; every acceptance criterion mapped to a test; recap and smoke-test checklist delivered.

#### Manual Verification:

- [ ] **Manual-verified**: run the smoke-test checklist from the recap.

## Testing Strategy

Each ticket item's Done-when test runs at its public boundary: the launcher command line, the `--close` command, a real `git merge`, and a real `zsh -i`. lane-status tests stub only `hunk-review-pane` and use real processes for liveness and RSS.

## References

- `./00-ticket.md`, `./02-research.md`, `./03-decisions.md`
- `docs/toolkit-script-rules.md`
