---
date: 2026-11-23
git_commit: 0236c779f360bdeae727873427c109718ae3b64c
branch: fix/lane-tools-nov23
topic: hunk review pane launch, lane status and close tooling, script platform handling, git hooks, zsh aliases, test conventions, change files
tags: [herdr, hunk, lanes, scripts, stow, githooks, zsh, tests, changes]
status: complete
---

# Research: hunk review pane launch, lane status and close tooling, script platform handling, git hooks, zsh aliases, test conventions, change files

## Findings

### 1. hunk-review-pane launch path and herdr-dev

- `herdr-dev` types the command into a pane's shell. It does not exec hunk. The right pane is made by `editor=$(split "$agent" 0.4)` then `run "$editor" "hunk-review-pane"` (`scripts/.local/bin/herdr-dev:142-145`). The nvim form is kept as two commented lines (`:143-144`).
- `run()` is `herdr-api pane send-text "$1" "$2"` then `herdr-api pane send-keys "$1" enter` (`herdr-dev:10-13`). `split()` is `herdr-api pane split "$1" --direction right --ratio "$2" --cwd "$dir" --no-focus | jq -r '.result.pane.pane_id'` (`herdr-dev:24-27`).
- Env setup in herdr-dev: `set -euo pipefail` and `export PATH="$HOME/.local/bin:$PATH"` (`herdr-dev:45-46`). `dir` is `cd "$dir" && pwd` of arg 1 (`:54-55`). `ws` defaults to `herdr-api pane current | jq -r '.result.pane.workspace_id // empty'` (`:60-62`). No other env is set for the pane.
- The pane's shell is a fresh interactive shell started by herdr in `--cwd "$dir"`. `zsh/.zshrc` is read by it. It defines `alias hw='hunk-review-pane'` (`zsh/.zshrc:277`) and a `hunk()` function that adds `--no-hunk-headers` for `diff|show|patch|pager|difftool` and for `stash` (`zsh/.zshrc:284-293`). `hunk-review-pane` is a bash script, so it calls the `hunk` binary, not that function.
- The `hunk-review-pane` header says "Env (PATH shims, EDITOR) is the caller's job" (`scripts/.local/bin/hunk-review-pane:23`). The script has `set -u` and no PATH export (`:28`).
- `hunk-review-pane` startup (`scripts/.local/bin/hunk-review-pane`):
  - Sources `../lib/handoff-command.bash` from `$(dirname "$(readlink -f "$0")")` (`:30-32`).
  - `--state-dir PANE_ID` prints `${XDG_RUNTIME_DIR:-$HOME/.cache}/hunk-review-pane/<id with chars outside [A-Za-z0-9_.-] replaced by _>` and exits 0 (`:36-44`).
  - `set_untracked_flag` runs `hunk-untracked-flag` and keeps its output as one array element (`:48-53`). `hunk-untracked-flag` prints `--exclude-untracked` when `git ls-files --others --exclude-standard` shows more than 200 files (`scripts/.local/bin/hunk-untracked-flag:9-14`).
  - `set_base_ref` (`:60-70`): `git symbolic-ref --short -q HEAD`. For `origin/main` then `origin/master`, the first one whose `refs/remotes/<ref>` verifies is used. If the branch name equals that default branch's name, `base_ref` stays empty. Otherwise `base_ref=$(git merge-base HEAD refs/remotes/<ref>)`. A detached HEAD or no origin default gives an empty `base_ref`.
  - Without `$HERDR_PANE_ID` (`:74-78`): `exec hunk diff ${base_ref:+"$base_ref"} --watch ${untracked_flag[@]+"${untracked_flag[@]}"} "$@"`.
  - With `$HERDR_PANE_ID`: `herdr-api pane rename "$HERDR_PANE_ID" review >/dev/null 2>&1 || true` (`:81`). It makes the state dir and exports `HUNK_REVIEW_HANDOFF=$dir/handoff` and `HUNK_REVIEW_PIDFILE=$dir/hunk.pid` (`:83-86`). It sets `trap 'rm -rf "$dir"' EXIT` (`:87`) and writes `$dir/root` from `git rev-parse --show-toplevel` or `pwd -P` (`:89-90`).
  - Loop (`:92-110`): removes handoff and pidfile, recomputes base and untracked flag, and runs `hunk diff ${base_ref:+"$base_ref"} --watch ${untracked_flag[@]+...} "$@"` (non-exec, `:97`). An absent or empty handoff file ends with `exit "$hunk_status"` (`:102`). Otherwise the first line is the target. A target that is not `lazygit` or `nvim` goes to `exec_handoff_tool` (message, read, return 1) then `exit 1` (`:107`). A known target runs `(cd "$repo_root" && exec_handoff_tool "$target")` and the loop continues (`:109`).
- `exec_handoff_tool` does `exec env -u HUNK_REVIEW_HANDOFF -u HUNK_REVIEW_PIDFILE "$1"` (`scripts/.local/lib/handoff-command.bash:19`). `is_handoff_target` accepts `lazygit | nvim` (`:4-9`).
- Other callers of `hunk-review-pane`: the `hw` alias (`zsh/.zshrc:277`); the `herdr-dev` layout comment (`herdr-dev:25`).
- The test `tests/scripts/test_hunk_review_pane.py` covers only the `pane rename` call (stubs `herdr-api`, `hunk`, `hunk-untracked-flag`).

### 2. lane_status.py

File: `claude/.claude/scripts/tools/lane_status.py`; wrapper `scripts/.local/bin/lane-status` is `exec python3 "$HOME/.claude/scripts/tools/lane_status.py" "$@"` (`lane-status:2`).

- Args: none or `--changes` only. Anything else prints the docstring to stderr and exits 2 (`lane_status.py:236-240`).
- Exit codes: 0 with nothing printed; 1 (`EXIT_PROBLEMS`) when lines are printed; 2 (`EXIT_FAILED`) on `StatusError`, `system_resources.ResourceReadError` or `herdr_agents.PaneCallError` (`:43-44, :242-246, :257`).
- Thresholds, environment variables with defaults (`:47-51`): `LANE_STATUS_MIN_MEMORY_GB` 8, `LANE_STATUS_MIN_SCRATCH_GB` 1, `LANE_STATUS_SCRATCH_CAP_GB` 4. `threshold_gb` raises `StatusError` for a non-number, a non-finite value or a negative one (`:60-71`).
- Memory (`memory_lines`, `:74-81`): `system_resources.memory_available_gb()`. None gives `memory: cannot read`. A value below the minimum gives `memory: <N.N> GB available, under <T> GB`.
  - Linux reads `MemAvailable` from `/proc/meminfo`. macOS runs `vm_stat` and `sysctl -n hw.pagesize` and sums the free, inactive and speculative pages. Any other platform returns None (`claude/.claude/scripts/lib/system_resources.py:14-17, 48-70`).
- Scratch (`scratch_lines`, `:84-99`): the root is `hook_input.claude_code_temp_root()`. Free space comes from `df -Pk` on the nearest existing folder (`system_resources.free_gb`, `system_resources.py:79-87`). A value below the minimum gives `scratch: <N.N> GB free on <dir>, under <T> GB`. If the root is a directory, `du -sk` gives its size (`tree_gb`, `system_resources.py:90-97`, exit 1 accepted). A size above the cap gives `scratch: <root> holds <N.N> GB, over <C> GB`.
- Per-process memory: nothing in this script reads per-process memory. Only system-wide available memory and scratch folder size are read.
- Lanes (`:155-173`): `lane_entries.all_entries()` (`:176-180`) gives every lane. `herdr_agents.claude_agents()` gives the agents of `herdr-api agent list` whose `agent == "claude"`. Per lane:
  - Worktree folder missing gives `<name>: dead (worktree gone)`.
  - No claude agent whose cwd is inside the worktree gives `<name>: dead (no agent)`.
  - Any such agent with `agent_status == "working"` gives None (no line).
  - Otherwise `idle_line` (`:137-152`) uses the first agent. It finds the transcript through `agent_session.value` and `session_registry.projects_dir().glob("*/<session>.jsonl")` (`:102-112`).
  - The last transcript record with `isApiErrorMessage is True` gives `dead (login expired)` when its message JSON, lowercased, contains one of `/login`, `401`, `authentication`, `oauth token` (`LOGIN_WORDS`, `:53`). Other API errors give `dead (api error)`.
  - `loop_transcript.LoopTranscript(transcript).open_dispatches()` above 0 gives `<name>: waiting on N background job(s)`. An unreadable transcript prints a stderr note and counts 0 (`:127-134`).
  - Otherwise `<name>: <agent_status or unknown>`.
- `--changes` (`:183-212, :248-253`): the state file is `$XDG_STATE_HOME or ~/.local/state` + `/lane-status/seen.json` (`script_utils.xdg_state_home`, `script_utils.py:1485`). It is a JSON object keyed by lane name plus `memory` and `scratch`, holding each line or null. It is rewritten with `write_text_atomically` on every `--changes` run. Printed lines are those that differ from the stored ones, plus `<name>: working` for a lane that had a line before and now has none. A closed lane (absent from the current report) prints nothing. An unreadable seen file prints a stderr note and starts fresh.
- Lane file source: `claude/.claude/scripts/lib/lane_entries.py` (see Q4).
- Output is plain text, one line per problem. When there are no lanes, only the memory and scratch entries are in the report (`:228-230`).
- Test: `tests/scripts/test_lane_status.py`; also `tests/scripts/test_system_resources.py`, `tests/scripts/test_herdr_agents.py`.

### 3. Platform handling in scripts/.local/bin and shared defaults in scripts/.local/lib

`systemd-run` and `systemctl --user`:
- No script under `scripts/.local/bin` or `scripts/.local/lib` mentions `systemd-run`, `systemctl` or `launchctl` (rg over those two folders returns none).
- `systemd-run` appears in `claude/.claude/scripts/lib/memory_cap_scope.py:21` (`CAPPED_PREFIX = f"systemd-run --user --scope --quiet -p MemoryMax={MEMORY_MAX} -p MemorySwapMax=0"`). `cap_available()` (`:41-45`) is true only when `sys.platform` starts with `linux`, `shutil.which("systemd-run")` finds it, and `$XDG_RUNTIME_DIR/bus` exists.
- `systemctl --user` appears in `install/daily-recap:94,132-135`, `install/weekly-recap:66,104-107`, `install/herdr-wake-limited:67,92-95`. Each branches `[[ "$(uname)" == "Darwin" ]]` (LaunchAgent plist, `install/herdr-wake-limited:36-`) then `command -v systemctl &>/dev/null && systemctl --user show-environment &>/dev/null` (systemd user timer).
- `claude/.claude/scripts/bash-safety-gate.sh:474-475` blocks `launchctl load` and `systemctl (enable|start)` in a Bash call.

Platform handling inside `scripts/.local/bin`:
- `detach:6-20`: `command -v setsid &>/dev/null && exec setsid "$@"`, else a perl `POSIX::setsid()` form (forks first for a group leader).
- `clip-image:9,23-40`: `command -v notify-send`; `xclip`/`wl-paste` for Linux; macOS needs `pngpaste` (message at `:37`).
- `hypr-screenshot:18-19`: `wl-copy`, `notify-send`.
- `bookmark:29`: `elif command -v xclip`.
- `ccusage-breakdown:31-56`: `date -j` probe selects macOS or GNU date; `STAT_FMT` mac or linux.
- `herdr-fleet:39`: `stat -c %Y "$f" || stat -f %m "$f"` (GNU then BSD).
- `agent-cost:128`: comment "GNU date first, BSD/macOS second".
- `achievement:54`: comment on `date -d 'monday this week'` being wrong with GNU date.
- `hunk-review-pane:73` and `hunk-review-popup:31`: the `${a[@]+...}` form for macOS bash 3.2 and empty arrays under `set -u`.
- `theme-mode:1988-1990, 2007, 2101, 2121`: macOS awk, app path, Ghostty Application Support path.
- `herdr-worktree-prune:67, 341-391`: `PROC_ROOT = "/proc"`; `proc_is_usable()`, `processes_from_proc()`, `processes_from_lsof()`, `read_processes()` choose `/proc` or `lsof`.
- `herdr-api:14-20`: `TUIOS_SOCKET` set means the tuios herdr shim is run with `HERDR_SOCKET_PATH="$TUIOS_SOCKET.herdr"`; otherwise `herdr` from PATH.
- `herdr-lane-resume`, `herdr-dev` and `herdr-worktree` branch on `TUIOS_SOCKET` (`herdr-lane-resume:82,107-119,126-130`; `herdr-dev:156,147`).

`scripts/.local/lib` files (all sourced bash):
- `toolkit-tools.bash` — sets `lanes_cli=${HERDR_LANES_CLI:-$HOME/.claude/scripts/tools/lanes.py}` and `session_pane=${HERDR_SESSION_PANE:-$HOME/.claude/scripts/tools/session_pane.py}` (`:5,7`). Its header says it is sourced by herdr-lane-resume, herdr-worktree, herdr-phase-change and herdr-worktree-watch (`:1`).
- `handoff-command.bash` — `is_handoff_target`, `exec_handoff_tool` (see Q1). Sourced by hunk-review-popup and hunk-review-pane.
- `location-args.bash` — `parse_location_args`, `resolve_location_files`, sourced by hunk-notes and nvim-jump.
- Library lookup in scripts: `. "$(dirname "$(readlink -f "$0")")/../lib/<file>"` (`herdr-lane-resume:31`, `hunk-review-pane:32`); `herdr-worktree:69` sources `"$script_dir/../lib/toolkit-tools.bash"`.
- Repo rule: a path or env default shared by two scripts goes in a sourced file under `scripts/.local/lib` (`CLAUDE.md`, Key Conventions).

### 4. herdr-lane-resume `--close`

File: `scripts/.local/bin/herdr-lane-resume`.
- Option parse (`:184-196`): `case "${1:-}"`. `-h|--help` prints the header lines via `usage` (`sed -n '2,/^$/s/^# \{0,1\}//p' "$0"`, `:33`). `--close` requires `$# -eq 2`, else `fail "--close needs one lane name"`, then `close_lane "$2"`. Other `-*` options: message, usage, exit 1. No argument: usage on stderr, exit 1. Otherwise exactly one positional name goes to `resume_lane`.
- `fail()` prints `herdr-lane-resume: <msg>` to stderr and exits 1 (`:35-38`).
- Lane lookup (`lane_entry`, `:46-56`): `python3 "$lanes_cli" get "$1"`, then `jq -c '.entry // empty'`. When empty it runs `python3 "$lanes_cli" list` and fails with `no lane named $1; known lanes: <names joined by spaces or "none">`. `lanes_cli` comes from `toolkit-tools.bash` (default `~/.claude/scripts/tools/lanes.py`).
- Lane file store: `claude/.claude/scripts/lib/lane_entries.py` owns `<${XDG_STATE_HOME:-~/.local/state}>/herdr-lanes/<name>.json` (`lanes_dir`, `:48-50`), the one lock `lanes.lock` (`:53-55`), and fields `name, worktree, main_checkout, branch, brief, session_id, reports_to, started_at` (`FIELDS`, `:18`). A name must match `^[A-Za-z0-9][A-Za-z0-9._-]*$` (`NAME_PATTERN`, `:19`). `entry(name)` returns None for a missing file (`:186-192`); `read_entry` raises `LaneFileError` on an unreadable or invalid file; `remove_entry` raises `LaneNotFoundError` (`:260-265`).
- `close_lane` (`herdr-lane-resume:146-182`):
  1. `HERDR_LANE_CLOSE_WAIT` (default 10) must match `^[0-9]+$`, else fail before any change (`:148-151`).
  2. `lane_entry` gives `wt` (`.worktree`) and `main_checkout`; `wt` goes through `real_path` when the folder exists (`:153-156`).
  3. `agents_in "$wt" "nothing changed" claude` (runs `session_pane.py agents-in <wt> claude`, `:62-69`); an agent with status `working` fails: `lane $name has a working agent in pane <p>; wait for it to finish, then rerun` (`:159-161`).
  4. `workspaces_on "$wt" "$name"` (`:73-86`) lists workspace ids; each is closed with `close_workspace` (`herdr-api workspace close` under tuios, else `herdr workspace close`, `:125-131`). A failed close fails with "the lane entry is kept and nothing was pruned" (`:163-167`).
  5. If any workspace was closed, `wait_for_agents_to_leave` polls `agents_in` every 0.5 s up to the wait seconds, then prints a stderr note "an agent still runs in <wt>; the prune will keep it" (`:133-144`).
  6. A missing worktree folder prints a stderr note and goes on (`:172`).
  7. `python3 "$lanes_cli" remove "$name" >/dev/null` removes the entry (`:173`).
  8. A missing main checkout prints `main checkout <path> is gone; nothing to prune` and returns 0 (`:175-178`).
  9. `(cd "$main_checkout" && "$bin_dir/herdr-worktree-prune" --apply)`; the function returns its status (`:179-181`).
- When no lane file entry matches, `--close <name>` exits 1 with `no lane named <name>; known lanes: ...` before anything changes (`:46-56`, called at `:153`).
- Worktree removal, prune and branch delete are done by `herdr-worktree-prune --apply` (`scripts/.local/bin/herdr-worktree-prune`):
  - `remove_one` (`:741-762`) re-checks the tree on a fresh world (`recheck`, `:729-738`), then `git worktree remove <path>` from the main checkout, never `--force`. A refusal prints `failed ...` and counts a failure.
  - `delete_branch_after_removal` (`:765-773`) calls `delete_branch` (`:839-858`): `branch_tip`, then `git merge-base --is-ancestor <tip> <compare hash>` (exit 1 means not on compare ref; other non-zero means git failure), then `git update-ref -d refs/heads/<name> <tip>`, then `remove_branch_config` for `branch.<name>`.
  - `prune_worktrees` (`:776-790`) prints `removed N, freed ... bytes (...), kept N, failed N` and returns 1 when any step failed.
  - Docstring: never `git branch -D`, `git worktree prune`, `git gc`, `git stash drop` (`:54-57`).
- Resume side (`resume_lane`, `:88-122`) is the other verb of the same script: stops when the worktree is gone, `session_id` is empty, an agent runs in the worktree, or a workspace is open on it; else opens a workspace (`herdr worktree open --cwd <main> --path <wt> --label <name> --focus`, or `herdr-api workspace create --cwd <wt> --label <name> --focus` under tuios) and runs `herdr-dev --resume <wt> <ws> <session> <brief>`.
- Test: `tests/scripts/test_herdr_lane_resume.py` (stubs `herdr`, `herdr-api`, `herdr-dev`, `herdr-worktree-prune`; real `lanes.py`).

### 5. herdr workspace listing, fields and merged-branch checks

- Listing command: `herdr-api workspace list`. A live run on this machine returned `{"id":"cli:workspace:list","result":{"type":"workspace_list","workspaces":[...]}}`. Each workspace object has: `active_tab_id`, `agent_status`, `focused`, `label`, `number`, `pane_count`, `tab_count`, `workspace_id` (for example `w5M`), and `worktree` with `checkout_path`, `is_linked_worktree`, `repo_key`, `repo_name`, `repo_root`.
  - The workspace for this lane has `label` `dotfiles-lane-tools-nov23` and `worktree.checkout_path` `/home/brandon/dotfiles-lane-tools-nov23`. A workspace with no worktree data has no `checkout_path`; the readers use `// ""`.
- `herdr-api` (`scripts/.local/bin/herdr-api:12-20`) passes args through to `herdr`, or to the tuios shim when `TUIOS_SOCKET` is set.
- `herdr-lane-resume` `workspaces_on` (`:73-86`): `jq -r '.result.workspaces[] | [.workspace_id, .label, (.worktree.checkout_path // "")] | join("\u001f")'`, compares `real_path(checkout)` to the worktree; under tuios it also matches `label == <lane name>`.
- `herdr-worktree-prune` (`:139-143, :412-422`): dataclass `Workspace(label, checkout_path)`; `workspaces_from_json` reads `parsed["result"]["workspaces"]`, `entry.get("label")`, `entry["worktree"]["checkout_path"]`. `check_herdr` (`:633-642`) keeps a tree when a workspace's real `checkout_path` is on it, or when a workspace with no `checkout_path` has `label == <tree folder name>`. Agent cwds come from `herdr-api agent list` `.result.agents[].cwd` (`:425-429`). One failed list is recorded in `state.herdr_failures` and not asked again (`:432-443`).
- `herdr-worktree` (`scripts/.local/bin/herdr-worktree`): does not list workspaces. It reads `.result.workspace.workspace_id` from the create reply (`:224`), and `herdr-api pane get ... .result.pane.agent` (`:293`). It does no merge check (rg for `merged|merge-base|is-ancestor` in that file finds none).
- `herdr-worktree-watch` (`:116-126`): `herdr-api workspace get "$workspace"`; the error code `workspace_not_found` means closed.
- `herdr-dev:114`: `herdr-api workspace get "$ws" | jq -r '.result.workspace.active_tab_id'`.
- Merged checks in `herdr-worktree-prune`:
  - Worktree: `check_merged` (`:560-570`): `git merge-base --is-ancestor <tree.head> <repo.compare_hash>`; exit non-zero other than 1 gives `CANNOT_CHECK`; otherwise `git rev-list --count <compare>..<head>` fills the `NOT_MERGED` text ("a squash or rebase merge looks ...").
  - Compare ref is `origin/<default branch>` from `refs/remotes/origin/HEAD` after `git fetch --quiet origin <default branch>`; the script stops with exit 1 when there is no repo, origin, `origin/HEAD`, or fetch fails (docstring `:29-34`, `start_up` `:665-`).
  - Branches with no worktree: `merged_free_branches` (`:914-`) uses `git for-each-ref --merged=<compare hash> --format=%(refname) refs/heads/`; `--branches` mode `prune_branches` (`:951-`).
  - Branch deletion re-checks ancestry (`:847`).
- Test: `tests/scripts/test_herdr_worktree_prune.py`, `test_herdr_worktree.py`, `test_herdr_worktree_watch.py`.

### 6. install/check-script-links and install/stow

- `install/check-script-links` (`:1-42`): for each regular file `$DOTFILES_DIR/scripts/.local/bin/*`, requires `[ "$HOME/.local/bin/<name>" -ef "$script" ]` (`:25-32`). `-ef` is true when both resolve to the same file, so a symlink, relative link or folded directory all pass.
  - On gaps: prints `✗ <name> is not linked from <target dir>` per script, then one `→` hint line, and `exit 1` (`:34-40`).
  - All linked: prints `✓ Every script in scripts/.local/bin is linked` and exits 0 (`:42`).
  - Uses `set -e`, and the `print_success`, `print_error`, `print_info` colour functions (`:9-17`).
  - Takes no arguments; `TARGET_DIR` is fixed to `$HOME/.local/bin`.
- Callers: `install/stow:103` (`"$DOTFILES_DIR/install/check-script-links" || LINKS_MISSING=1`); `tests/scripts/test_check_script_links.py`. No other caller in the repo outside `docs/changes`.
- `install/stow` relink of `scripts`: `PACKAGES="nvim scripts zsh claude opencode omp pi ghostty kanata starship git lazygit herdr tuios hunk zed ripgrep"` (`:67`), plus `hypr quickshell gtk qt` on arch (`:70-72`) and `aerospace` on mac (`:75-77`). One loop runs `stow -R "$pkg" 2>/tmp/stow-$pkg.err` per package (`:84-93`); a failure is appended to `FAILED`, its stderr printed, and the run later prints `Unstowed packages:` and exits 1 (`:95-99`). `cd "$DOTFILES_DIR"` happens at `:20`, so `stow -R scripts` links relative to the repo folder that holds the script (the repo the install script is in). After `✓ Symlinks created` it runs the link check (`:100-103`), does the macOS Ghostty and lazygit steps, then `[ -z "${LINKS_MISSING:-}" ] || exit 1` (`:136`).
- Pre-stow steps: `mkdir -p ~/.config/tuios/config.d` (`:64`), backups of nvim, zshrc, claude, opencode, zed files, hypr (`:23-59`).
- `~/.local/bin` on this machine links through to the main checkout (`/home/brandon/dotfiles`) as seen in earlier plan notes (`docs/plans/herdr-tools-1122/review-round1-shard-a.md:14`).

### 7. .githooks, core.hooksPath, hook types, pull_keep_index.py

- `.githooks/` holds one file: `.githooks/pre-commit` (bash, `set -euo pipefail`).
  - It refuses a commit whose staged paths match `^claude/\.claude/(agents|skills|commands|hooks|scripts)/|^claude/\.claude/CLAUDE\.md$` when no added or modified `docs/changes/notes/20*.md` is staged (`:9-23`). The message names `python3 ~/agent-evals/bin/build_changes.py new "<title>" --by claude-code/<model id>`.
  - It then runs `python3 "$AGENT_EVALS_DIR/bin/build_changes.py" --check --root docs/changes` (`AGENT_EVALS_DIR` default `~/agent-evals`, `:7-8, :30`); exit 1 on failure. If `build_changes.py` is missing it warns and exits 0 (`:25-28`).
  - Header comment: "Enable with: git config core.hooksPath .githooks" (`:3`).
- `core.hooksPath`: `git config --show-origin --get-all core.hooksPath` returns `file:/home/brandon/dotfiles/.git/config  .githooks` (set in the main checkout's repo config, which linked worktrees share). No script under `install/`, `setup`, `CLAUDE.md` or `.github` sets it (rg for `hooksPath|githooks` there finds nothing).
- `/home/brandon/dotfiles/.git/hooks` holds no non-sample hook files.
- Hook types referenced in the repo: the only hook file is `pre-commit`. `tests/scripts/test_pre_commit_hook.py` tests it. `claude/.claude/scripts/gates` and `tests/scripts/test_git_discipline_gate.py:536-826` reference `core.hooksPath` overrides and `--no-verify` as denied forms (lines `536, 537, 576, 783-826`). `bash-safety-gate.sh:292` has `git (commit|push|merge) ... --no-verify` and `.git/hooks/` write patterns. No `post-merge`, `post-checkout`, `post-commit` or `pre-push` hook file exists in the repo (rg of those names finds only `docs/` text and change notes).
- `claude/.claude/scripts/tools/pull_keep_index.py` exists. Usage (`:1-3`): `<repo>`, `--put-back <saved> <repo>`, `--help`.
  - Pull path (`run_pull`, `:769-805`): refuses if a rebase is stopped (`stopped_rebase_dir`); `upstream_relation` can report "already held" or "rewritten locally" with exit 0; `pull_target`; with tracked changes and another live session in the repo it takes the shared route (`shared_pull`, no set-aside); otherwise `set_aside` (a `git stash create` commit kept under `refs/pull-keep-index/<UTC stamp>-<8 of commit>`, `:272-286`), `git -C <repo> pull --rebase=merges --no-autostash <target>` (`:791`), then `merge_in_place_of_rebase` when the rebase stops (`:190-222`), then `put_back` (`:493-514`), `exit_if_upstream_gone`, `set_upstream`.
  - `put_back` restores staged files staged. When staged changes clash on `merge=built-page` paths and `merge.built-page.driver` is configured, it runs `put_back_by_hand` (`:447-476`) with `BUILT_PAGE_STASH` set (`:76`). Lock file `<git common dir>/pull-keep-index.lock`, `PULL_KEEP_INDEX_LOCK_SECONDS` default 300 (`:70-72`).
  - After a merge: the script calls `git merge` only in `merge_in_place_of_rebase` (`:190-222`) and `merge_abort_text` (`:181-187`); it installs and calls no git hook.
- The global rule in `~/.claude/CLAUDE.md` runs this script right before `git push -u origin HEAD`.

### 8. zsh/.zshrc

- `~/.zshenv` (`zsh/.zshenv:1-3`) exports only `RIPGREP_CONFIG_PATH` and notes it is read by every zsh, "including the non-interactive shells that Claude Code's Bash tool and hooks start. .zshrc is read only by interactive shells."
- `ls` and `cat` aliases (`zsh/.zshrc:379-383`):
  ```
  # Claude Code's Bash tool loads these aliases too; there GNU flags (ls -t, ls -d) must reach the real ls and cat.
  if [[ -z "$CLAUDECODE" ]]; then
      alias cat="bat --plain"
      alias ls="eza --icons=auto"
  fi
  alias ll="eza --icons -lha"
  alias lt="eza --icons --tree --level=2"
  ```
  `ll` and `lt` are defined whether or not `CLAUDECODE` is set. The file has no `$-`, `[[ -o interactive ]]` or other interactive guard (rg for `interactive|\[\[ -o|\$-` finds only comments).
- Other `CLAUDECODE`/`CLAUDE_CODE` references in `zsh/.zshrc`: none. `CLAUDE_SKIP_HOOKS` appears in `alias ccskip="CLAUDE_SKIP_HOOKS=1 claude"` (`:279`).
- Other aliases and functions (`zsh/.zshrc`): `kill_port()` (`:88`), `mprocs()` (`:101`), django aliases `dj*` (`:109-116`), git aliases `gcm gcb gf gp gmom grom gpou gpffetch ga gcom gs gstat` (`:120-131`), `gwa()` (`:134`), `rsd rwe rds rfs rtqa` (`:136-140`), `brew86`, `brewARM` (`:142-143`), `rl vc vv vd vn hw cc ccskip oc` (`:272-280`), `hunk()` (`:284`), `cw()` (`:303`), `cwc()` (`:351`), `headroom-stats` (`:378`), `fd` alias to `fdfind` when `fd` is absent (`:386`), `theme-mode()` (`:430`).
- Init code that differs by environment:
  - `~/.zshrc.local` is sourced at the top (`:1-2`) and again at `:296`.
  - PATH `~/.local/bin` is exported first (`:12`) and again after linuxbrew (`:~393`).
  - Multiplexer autostart is guarded by `[ -z "${HERDR_TAB_ID}${HERDR_PANE_ID}${HERDR_SOCKET_PATH}${TUIOS_SESSION}" ]` (`:42, :49`); `MUX=tuios` in `~/.zshrc.local` picks tuios (`:36`).
  - Undercurl TERM swap runs only when `HERDR_ENV = 1`, `TERM = xterm-256color`, `TERM_PROGRAM = ghostty` and `infocmp xterm-ghostty` works (`:70-71`).
  - herdr-automatic-rename shell hook is sourced when `herdr` exists and the plugin glob matches (`:257-268`).
  - `cw()` branches on `HERDR_PANE_ID` (`:326`).
  - kiro shell integration on `TERM_PROGRAM == kiro` (`:389`), linuxbrew shellenv when the file exists, flatpak XDG dirs, keychain on Linux, bun, cargo, atuin init (`command -v atuin`), `BUN_OPTIONS` preload when `~/.local/share/no-agent-summary.js` exists (`:439-441`).
- Claude Code shell snapshots: nothing in the repo names a snapshot file. `CLAUDECODE` is the only agent-shell variable `.zshrc` tests.
- Tests that read `.zshenv`: `tests/scripts/test_ripgrep_config.py` (a `zsh` non-interactive test, skipped if `zsh` is missing). No test reads `.zshrc` (rg for `zshrc` in `tests` returns only `gate_replay_corpus.json`, `test_adr_flow.py`, `test_toolkit_self_location.py`, `test_ripgrep_config.py`).

### 9. Test patterns

- Runner: `tests/run.sh` (bash, `set -euo pipefail`). Steps in order: `tests/lint.sh`; a suite-receipt start tree; `tests/duplicate_code.py`; a snapshot of the review-gate folder (`tests/review_gate_unchanged.py snapshot`); `python3 tests/parallel_tests.py` with `TMPDIR` set to a run temp folder; gate compare; failed steps are named on a last `FAILED:` line, exit 1 (`:19-75`). A markdown-only change runs only files `tests/changed_scope.py kept` names (`:42-49`).
- `tests/parallel_tests.py`: runs each `tests/scripts/test_*.py` (glob `SCRIPTS_TESTS.glob("test_*.py")`, `:75`) as its own process, `nproc` at a time, largest first. It accepts file names (`parallel_tests.py test_a.py`), exits non-zero on an unknown name (`:80`). `SHARDS = {"test_review_loop_script.py": 4}` (`:40`).
- Tests are `unittest` files in `tests/scripts/`; `tests/scripts/toolkit_paths.py` gives `CLAUDE_DIR`, `SCRIPTS_DIR`, `TOOLS_DIR`, `LIB_DIR`, `REPO_ROOT`, `RIPGREP_CONFIG`, `ZSHENV_DIR` etc.
- Shell scripts in `scripts/.local/bin`: tests with `test_herdr_*.py`, `test_hunk_review_pane.py`, `test_lane_status.py`, `test_check_script_links.py`. Pattern in `tests/scripts/stubs.py` (`write_stub(path, body)` writes `#!/bin/bash` + body, mode 0755, `:16-18`). The test puts a stub folder first on `PATH` and sets `HOME` to a temp folder (`test_hunk_review_pane.py:26-33`, so `herdr-api` stubs win over `~/.local/bin`). A stub for `herdr-api` appends `"$*"` to an args or events file (`test_hunk_review_pane.py:25`, `test_herdr_lane_resume.py:34-61`). `test_herdr_lane_resume.py` copies the script beside stubs for `herdr-dev` and `herdr-worktree-prune`, sets `STATE_DIR` and `EVENTS` env vars, and builds `agents.json` and `workspaces.json` in `STATE_DIR` for the stub to `cat` (`:34-70`). Env overrides for tools: `HERDR_LANE_RESUME`, `HERDR_LANES_CLI`, `SESSION_PANE_SCRIPT` (`:19-22`).
- `stubs.run_through_stow_symlink(script, scratch, *args)` runs a copy through a symlink in a separate bin folder (`stubs.py:21-35`); `stubs.copy_toolkit_tools_lib(root)` copies `toolkit-tools.bash` to `<root>/lib` (`:9-13`).
- Git hook test: `tests/scripts/test_pre_commit_hook.py` takes the hook path from env `PRE_COMMIT_HOOK` (default `.githooks/pre-commit`, `:7`), makes a temp git repo, stages files with `git add`, writes a fake `build_changes.py` that prints its args and exits with a chosen code (`install_checker`, `:41-47`), and runs the hook with `AGENT_EVALS_DIR` set (`:49-51`).
- Install script test: `tests/scripts/test_check_script_links.py` builds a temp `HOME` with `.local/bin` symlinks, runs the script with `{"PATH": ..., "HOME": ...}` (`:25-30`).
- zsh test: `tests/scripts/test_ripgrep_config.py` (`.zshenv` through a non-interactive zsh, `@unittest.skipUnless(shutil.which("zsh"))`).
- No doctor-style probe test exists. rg for `doctor` in `tests/` finds only `gate_replay_corpus.json` and `test_adr_flow.py`.
- Rules for new toolkit script tests: `docs/toolkit-script-rules.md` "Tests" (file `tests/scripts/test_<script>.py`, env var for script path, run through `python3 tests/parallel_tests.py <file>`, `bash tests/lint.sh <changed .py files>`).

### 10. Change files

- `~/agent-evals/bin/build_changes.py` exists. `build_changes.py new --help`: `new [-h] [--date DATE] --by BY [--root ROOT] title`. `--by` is `<producer>/<version>`, `human:<id>` or `process:<id>`. `--date` is `YYYY-MM-DD`, default now. Top-level options `--root` (default `docs/changes` of the dotfiles checkout at cwd), `--watches`, `--findings`, `--queue`, `--watch-readings`, `--check`, `--lenient-findings`. `new` writes an unfilled `<date>-<slug>.md`.
- Storage: `docs/changes/notes/<YYYY-MM-DD>-<slug>.md`; `docs/changes/` also holds `changelog.md`, `fixes-by-script.md`, `index.md`, `in-progress.md`, `ruled-out.md`, `what-worked.md`. The pre-commit hook pattern is `^docs/changes/notes/20[^/]*\.md$` (`.githooks/pre-commit:10`). Latest notes at this commit are dated `2026-11-23-*.md`.
- Format (example `docs/changes/notes/2026-10-30-install-flags-any-script-it-left-unlinked.md`): YAML frontmatter with keys `type: "Change"`, `change_type: "fixed"`, `title`, `description`, `generated: {"by": "claude-code/claude-sonnet-5-5", "at": "<ISO time with offset>"}`, `seq`, `kind: "fix"`, `components: ["script/install-stow", ...]`, `evidence: ["judgment"]`, `watches: []`, `test: "<test path>::<Class>::<method>"`, `asked: ""`, `proof: []`, `unmeasured: ""`. Body sections in order: `## Change`, `## Evidence`, `## Result`, `## Watch`, `## Back-out`.
- `docs/changes/changelog.md` has one line per note; for the example note at `:652` the line links `notes/<file>.md`, adds `[script/install-stow, script/herdr-phase-change]` and the description.
- The `--check` mode is what the pre-commit hook runs.

## Dormant scaffolding

- `scripts/.local/bin/herdr-dev:143-144`: two commented lines (`herdr-api pane rename "$editor" editor`, `run "$editor" "nvim ."`) kept as the nvim alternative.
- `scripts/.local/lib/handoff-command.bash` `is_handoff_target` accepts only `lazygit | nvim`; the `hunk-review-pane` header names both.
- `lane_entries.FIELDS` includes `started_at`, `reports_to`, `brief`; `lane_status.py` reads only `name`, `worktree` from lane entries (`lane_status.py:158,161,173`).
- `herdr-worktree-prune` `Workspace` dataclass (`:140-143`) has `label`, `checkout_path`; `Herdr.note` (`:150`) is set only when a list failed.
- `.githooks/` holds one hook; `core.hooksPath` is set in `/home/brandon/dotfiles/.git/config`, with no repo script that sets it.
- `docs/changes/notes` frontmatter keys `watches`, `asked`, `proof`, `unmeasured` hold empty values in the sampled note.

## Code References

- `scripts/.local/bin/herdr-dev:142-145` — types `hunk-review-pane` into the right pane.
- `scripts/.local/bin/herdr-dev:45-46` — `set -euo pipefail`, PATH prefix.
- `scripts/.local/bin/hunk-review-pane:60-70` — `set_base_ref`.
- `scripts/.local/bin/hunk-review-pane:74-78` — no-herdr exec of `hunk diff ... --watch`.
- `scripts/.local/bin/hunk-review-pane:92-110` — handoff loop.
- `scripts/.local/lib/handoff-command.bash:4-20` — handoff target check and exec.
- `claude/.claude/scripts/tools/lane_status.py:47-51` — thresholds.
- `claude/.claude/scripts/tools/lane_status.py:155-173` — per-lane lines.
- `claude/.claude/scripts/lib/system_resources.py:64-97` — memory, `df`, `du` reads.
- `claude/.claude/scripts/lib/lane_entries.py:18-19, 48-55, 186-192, 260-265` — lane file fields, dir, lookup, remove.
- `claude/.claude/scripts/lib/herdr_agents.py:17-63` — `herdr_reply`, `listed_agents`, `claude_agents`, `agents_in`.
- `scripts/.local/bin/herdr-lane-resume:184-196` — option parse.
- `scripts/.local/bin/herdr-lane-resume:146-182` — `close_lane`.
- `scripts/.local/bin/herdr-lane-resume:73-86` — `workspaces_on`.
- `scripts/.local/bin/herdr-worktree-prune:560-570, 741-773, 839-858` — merged check, removal, branch delete.
- `scripts/.local/bin/herdr-worktree-prune:412-422, 633-642` — workspace read and herdr check.
- `scripts/.local/bin/herdr-api:12-20` — herdr or tuios shim.
- `scripts/.local/lib/toolkit-tools.bash:5,7` — `lanes_cli`, `session_pane`.
- `install/check-script-links:25-42` — link check.
- `install/stow:67, 84-93, 103, 136` — package list, per-package stow, link check call, final exit.
- `.githooks/pre-commit:9-33` — change-file and ledger check.
- `claude/.claude/scripts/tools/pull_keep_index.py:769-805` — `run_pull`.
- `claude/.claude/scripts/lib/memory_cap_scope.py:21, 41-45` — systemd-run prefix and availability.
- `zsh/.zshrc:277, 284-293, 379-386` — `hw`, `hunk()`, `CLAUDECODE` guard.
- `zsh/.zshenv:3` — `RIPGREP_CONFIG_PATH`.
- `tests/run.sh:19-75` — suite steps.
- `tests/parallel_tests.py:75-80` — test file glob and name check.
- `tests/scripts/stubs.py:9-35` — stub helpers.
- `tests/scripts/test_pre_commit_hook.py:7, 41-51` — hook test harness.
- `docs/changes/notes/2026-10-30-install-flags-any-script-it-left-unlinked.md` — change file example.

## Patterns Found

- Bash scripts find their sourced library through `readlink -f "$0"` (`herdr-lane-resume:31`, `hunk-review-pane:32`).
- Scripts under `scripts/.local/bin` call toolkit Python through env-overridable paths: `HERDR_LANES_CLI`, `HERDR_SESSION_PANE`.
- Multiplexer choice is a `TUIOS_SOCKET` test (`herdr-api`, `herdr-lane-resume`, `herdr-dev`).
- Platform probes are by tool or flag presence (`command -v setsid`, `date -j`, `stat -c || stat -f`), by `uname` (`install/*`), or by `sys.platform` (`system_resources.py`, `memory_cap_scope.py`).
- Python tools read herdr through `herdr-api` as JSON (`herdr_agents.herdr_reply`); bash tools use `jq` on `herdr-api` output; `herdr-worktree-prune` has its own parser for the workspace list.
- Failures: bash `fail()` prints `<script>: <msg>` and exits 1; python tools print `<tool>: <msg>` to stderr and exit 2.
- Install scripts share `print_success`, `print_error`, `print_info` and `set -e`.
- Tests stub external commands with generated `#!/bin/bash` files put first on PATH, record calls in a file, and set `HOME` to a temp folder.
- Lane state is one JSON file per lane under `${XDG_STATE_HOME:-~/.local/state}/herdr-lanes/`; `lane-status` state is `.../lane-status/seen.json`.

## Reuse Inventory

- `write_stub(path, body)` — `tests/scripts/stubs.py:16` — writes an executable bash stub.
- `copy_toolkit_tools_lib(root)` — `tests/scripts/stubs.py:9` — copies `toolkit-tools.bash` beside a script copy.
- `run_through_stow_symlink(script, scratch, *args)` — `tests/scripts/stubs.py:21` — runs a script copy via a symlink like stow.
- `toolkit_paths` constants — `tests/scripts/toolkit_paths.py:12-30` — toolkit folder paths.
- `is_handoff_target(target)`, `exec_handoff_tool(target)` — `scripts/.local/lib/handoff-command.bash:4,13`.
- `parse_location_args`, `resolve_location_files` — `scripts/.local/lib/location-args.bash:11,42`.
- `lanes_cli`, `session_pane` variables — `scripts/.local/lib/toolkit-tools.bash:5,7`.
- `lane_entries.all_entries() → list[dict]`, `entry(name) → dict|None`, `entry_containing(path) → dict|None`, `entry_files()`, `read_entry(file)`, `read_named_entry(file)`, `validate_entry(data, file)`, `add_entry(...)`, `set_session(name, session_id, brief=None)`, `remove_entry(name)`, `lanes_dir()`, `lane_file(name)`, `lane_lock_path()` — `claude/.claude/scripts/lib/lane_entries.py:48-265`.
- `herdr_agents.herdr_reply(words) → dict`, `listed_agents()`, `claude_agents()`, `agents_in(directory, agents)` — `claude/.claude/scripts/lib/herdr_agents.py:17,37,47,52`.
- `system_resources.memory_available_gb()`, `free_gb(folder)`, `tree_gb(folder)`, `parse_meminfo_gb(text)`, `parse_vm_stat_gb(text, page_size)` — `claude/.claude/scripts/lib/system_resources.py:64,79,90,24,32`.
- `script_utils.xdg_state_home()`, `path_is_under(path, prefix)`, `nearest_existing_folder(path)`, `run_or_raise(argv, error_type, ...)`, `last_transcript_record(path)`, `write_text_atomically(path, content)`, `read_ledger(args, wait_seconds)` — `claude/.claude/scripts/lib/script_utils.py:1485,555,1389,600,1027,1445,779`.
- `hook_input.claude_code_temp_root()` — `claude/.claude/scripts/lib/hook_input.py:281`.
- `memory_cap_scope.cap_available()` — `claude/.claude/scripts/lib/memory_cap_scope.py:41`.
- `session_pane.py agents-in FOLDER [KIND]`, `resolve`, `sender` — `claude/.claude/scripts/tools/session_pane.py:152-164`.
- `lanes.py get|list|remove|add` — `claude/.claude/scripts/tools/lanes.py` (used by `herdr-lane-resume:48,51,173`, `herdr-worktree-prune`).
- `herdr-api` — `scripts/.local/bin/herdr-api` — herdr or tuios shim passthrough.
- `herdr-worktree-prune [--apply] [--branches]` — `scripts/.local/bin/herdr-worktree-prune`.
- `detach <command...>` — `scripts/.local/bin/detach` — setsid with perl fallback.
- `hunk-untracked-flag` — `scripts/.local/bin/hunk-untracked-flag`.
- `pull_keep_index.py <repo>` / `--put-back <saved> <repo>` — `claude/.claude/scripts/tools/pull_keep_index.py:1-3`.
- `build_changes.py new <title> --by <actor> [--date D] [--root R]`, `--check` — `~/agent-evals/bin/build_changes.py`.
- `install/check-script-links` — whole-package link check (no arguments).
- `install/` colour helpers `print_success`, `print_error`, `print_info` — copied at the top of each install script, e.g. `install/stow:10-12`.
