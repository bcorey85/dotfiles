---
date: 2026-11-22
git_commit: 8436be97f25cd96ffa9f4ae8c72f37ff32173768
branch: fix/herdr-tools-nov22
topic: herdr worktree, phase-change, review-pane and pull-keep-index tooling as they exist today
tags: [herdr, herdr-worktree, herdr-worktree-prune, herdr-phase-change, hunk-review-pane, nvim-jump, pull_keep_index, tests]
status: complete
---

# Research: herdr worktree, phase-change, review-pane and pull-keep-index tooling

Path note: `herdr-worktree` is at `scripts/.local/bin/herdr-worktree` (not under `claude/.claude/scripts/tools/`, which has no such file). `pull_keep_index.py` is at `claude/.claude/scripts/tools/pull_keep_index.py`. `claude/.claude` is a hidden folder: `rg` needs `--hidden` to search it.

## Findings

### 1. How `herdr-worktree` works end to end

File: `scripts/.local/bin/herdr-worktree` (280 lines, bash, `set -euo pipefail`, line 52).

Invocation and arguments (lines 58-99): `[--fork --prompt-file <path> | --fork --prompt <text>] [--base <ref>] [branch]`. `--prompt-file` is read with `cat` into `prompt` (line 93). `--fork` requires a brief; `--prompt`/`--prompt-file` require `--fork` (lines 96-99). One branch only (line 84).

Pre-checks, before anything is created:
- `herdr-api` must be on PATH (lines 101-102).
- With `--fork`: `detach` and `herdr-worktree-watch` must be executable in the script's own dir (`bin_dir`, lines 109-127); otherwise it prints a `stow -d ... -R scripts` command and exits 1. `HERDR_WORKTREE_WATCH_SECONDS` (default 120) must match `^(0|[1-9][0-9]*)$`; `HERDR_WORKTREE_FORK_TIMEOUT` (default 30) must be a whole number >= 1 (lines 104-135).
- Branch comes from args, else `fzf --print-query` as a one-line prompt (lines 138-145; Esc = exit 130 from fzf, script exits 0 at line 144). Empty branch exits 1 (146).
- `checkout=$(git rev-parse --show-toplevel)`; `main_checkout` = parent of `git rev-parse --git-common-dir` (lines 148-150).

Base ref (lines 152-167): default `HEAD`. Without `--fork`, when `origin` exists, base becomes `origin/HEAD`'s short name (`git symbolic-ref --short refs/remotes/origin/HEAD`) and `git fetch --quiet origin <default branch>` runs (fetch failure prints a note and continues). With `--fork` the base stays `HEAD`.

Worktree path (lines 169-180): branch matching `^([A-Z]+-[0-9]+)` gives suffix = ticket number; else suffix = branch with `feature/`, `fix/` removed and `/` -> `-`. Path = `<parent of main checkout>/<repo>-<suffix>`; if that exists, `<repo>-<branch with / -> ->`; if that exists too, exit 1.

Fork session read (lines 182-187): `herdr-api pane current | jq` selects `.result.pane.agent == "claude"` and takes `.result.pane.agent_session.value`; empty exits 1 ("--fork needs a claude pane").

Creation (lines 189-214):
- Under tuios (`TUIOS_SOCKET` set): `git -C $checkout worktree add -b <branch> <worktree> <base>` then `herdr-api workspace create --cwd <worktree> --label <folder name> --focus`.
- Under herdr: if run from a linked worktree, base is resolved to a commit hash first (lines 202-205); then `herdr worktree create --cwd <main checkout> --branch --base --path --label --focus`.
- Workspace id read from `.result.workspace.workspace_id`; missing id exits 1 echoing the reply (lines 210-214).

Post-create steps:
- `.python-version` link: when the worktree lacks it, the main checkout has the file, and `git check-ignore -q .python-version` holds, symlink it from the main checkout (lines 219-223).
- Node installs (lines 228-246): `git ls-files` for `package-lock.json`/`pnpm-lock.yaml` at root or one folder down; each runs `npm ci --no-audit --no-fund` or `pnpm install --frozen-lockfile` in its folder, output appended to `herdr-worktree-install.log` at `git -C <worktree> rev-parse --path-format=absolute --git-path herdr-worktree-install.log`. A missing tool or failed install warns on stderr and continues.
- `herdr-api workspace focus "$ws"` (line 250).
- `herdr-dev "$worktree" "$ws" "$claude_session" "$prompt"` run; its stdout line 1 = claude pane id, line 2 = typed command (lines 253-255).
- Push (lines 257-260): when the worktree has an `origin` remote, `git -C <worktree> push -u origin <branch>`; failure prints the retry command, does not stop the run.
- Without `--fork`: `exit 0` (line 262). Nothing printed on stdout by `herdr-worktree` itself; its messages go to stderr.

`--fork` tail (lines 264-280): polls `herdr-api pane get <claude pane>` once per second up to `fork_timeout` for `.result.pane.agent == "claude"`. On success it resolves `watch_log` (`git rev-parse --path-format=absolute --git-path herdr-worktree-watch.log`), starts `detach herdr-worktree-watch <ws> <worktree> <main checkout> <claude pane> <claude_session>` in the background with stdout/stderr appended to `watch_log` and `disown`, prints `herdr-worktree: watching workspace ...` to stderr and exits 0. On timeout it prints the pane id and the typed command (`claude_cmd`) to stderr and exits 1 (line 279-280).

`herdr-dev` (`scripts/.local/bin/herdr-dev`) as called here:
- Renames the active tab `code` and the first pane `claude` (lines 104-109). With a session id the typed command is `claude --resume <id> --fork-session --name <worktree folder name>`; with a start prompt it appends ` -- "$(cat '<mktemp file>')" && rm -f '<file>'` (lines 110-123). The temp file is written with `mktemp` (line 119) and removed only when claude exits cleanly.
- Splits the right pane at 0.4, renames it `review`, runs `hunk-review-pane` in it (lines 128-132). Creates a `console` tab with three panes, runs `mprocs --config` in pane 1 if an mprocs config exists (lines 140-161). Focuses the code tab, then the pane to the right of claude (165-166). Prints `$agent` and `$claude_cmd` (line 168).

What happens when a forked workspace closes: `scripts/.local/bin/herdr-worktree-watch` (126 lines), args `<workspace id> <worktree> <main checkout> <claude pane> <parent session>` (exactly 5, line 31):
- Log path `git -C <worktree> rev-parse --path-format=absolute --git-path herdr-worktree-watch.log` (line 38).
- Polls `herdr-api pane get <claude pane>` for `.result.pane.agent_session.value` until it is non-empty and differs from the parent session, bounded by `HERDR_WORKTREE_WATCH_SECONDS` (lines 58-75); a value equal to the parent after the wait is treated as empty (line 75). Then sleeps the remainder of the wait (lines 77-81).
- `herdr-api workspace get <ws>`: success appends `workspace <ws> still open` to the log and exits 0 (lines 83-86). Failure: `.error.code` must be `workspace_not_found`, otherwise prints `could not check workspace` to stderr, exit 1 (lines 91-95).
- On `workspace_not_found`, appends to the log (lines 112-122): `workspace <ws> closed. Recovery steps:`, then `1. herdr worktree open --cwd <main> --path <worktree> --focus` (tuios: `herdr-api workspace create --cwd ... --label ... --focus`), then with a session id `2. herdr-dev <worktree> <ws> <session> '<RESUME_PROMPT>'` (tuios prefixes `herdr-api workspace focus <ws> >/dev/null && `) plus the line `<ws> is the workspace id that step 1 prints (.result.workspace.workspace_id)`; without a session id `2. the fork's session id could not be read; run claude --resume in <worktree>`. `RESUME_PROMPT` is at line 44.
- Then (herdr only; tuios exits 0 at line 124) `herdr notification show "herdr-worktree: workspace closed" --body "... recovery steps are in <log>" --sound request` (lines 125-126). It never reopens the workspace (header lines 25-26).

### 2. State persisted by the herdr worktree tooling and where

All inside the worktree's per-worktree git dir, resolved with `git rev-parse --path-format=absolute --git-path <name>` (for this worktree: `/home/brandon/dotfiles/.git/worktrees/dotfiles-herdr-tools-nov22/<name>`, checked by running the command). For the main checkout that resolves under its own `.git/`. They sit outside the worktree's working tree.
- `herdr-worktree-install.log` — appended by `herdr-worktree:230,244`.
- `herdr-worktree-watch.log` — appended by `herdr-worktree:268-272` (watcher stdout/stderr) and `herdr-worktree-watch:38,84,112-122` (`still open` line, recovery steps).
- Temp brief file: `mktemp` file written by `herdr-dev:119-120`, outside the repo; removed by the typed command after a clean claude exit (`herdr-dev:121`).
- `.python-version` symlink inside the worktree (`herdr-worktree:221`).
- `hunk-review-pane` state dir (not a worktree file): `${XDG_RUNTIME_DIR:-$HOME/.cache}/hunk-review-pane/<pane id sanitized>/` holding `root`, `handoff`, `hunk.pid`; removed by `trap 'rm -rf "$dir"' EXIT` (`hunk-review-pane:36-38,80-87`).
- The existing tooling writes no "lane file", no persisted record of the fork session id, and no per-worktree record of the ticket or parent beyond the two logs above. `herdr-worktree-prune` reads git/herdr state and writes none (see Q3). No other herdr-tool script under `scripts/.local/bin/` was found writing under the worktree's git dir (`rg` for `--git-path` finds only the two scripts above).
- Recovery-step records exist only as the text in `herdr-worktree-watch.log`; the herdr `workspace` object carries `worktree` metadata (`checkout_path`, `is_linked_worktree`, `repo_key`, `repo_name`, `repo_root`) from herdr itself (observed in `herdr-api workspace list`).
- The Claude live-session registry (`~/.claude/sessions/<pid>.json`, fields `name`, `sessionId`, `pid`, `cwd`) is read by `claude/.claude/scripts/lib/session_registry.py:1-80`, not by these scripts.

### 3. `herdr-worktree-prune`: merged/clean decision and callers

File: `scripts/.local/bin/herdr-worktree-prune` (949 lines, python3). Usage `herdr-worktree-prune [--apply] [--branches] [-h|--help]` (line 4, `USAGE_LINE` 69). Unknown args: stderr + exit 2 (`main`, 927-936).

Start-up (`start_up`, 623-): requires a git repo, an `origin` remote, `refs/remotes/origin/HEAD`, then `git fetch --quiet origin <default branch>` (timeout 120 s); `origin/<default>` must resolve. `PruneError` -> stderr `herdr-worktree-prune: <msg>`, exit 1 (944-946). `Repo.compare_hash` is the fetched `origin/<default>` commit.

Per-worktree decision, `CHECKS` tuple at line 608, run in order by `evaluate` (612-620), first failing check returns a `Keep(code, text)`:
`check_main`, `check_current`, `check_bare`, `check_folder`, `check_locked`, `check_detached`, `check_default`, `check_merged` (518), `check_tree_state` (530), `check_stash` (570), `check_process` (581), `check_herdr` (591).
- Merged: `git merge-base --is-ancestor <tree.head> <compare_hash>` in the main path (519); exit 1 -> `NOT_MERGED` with `git rev-list --count` text noting squash/rebase merges look unmerged (522-527).
- Clean: `git status --porcelain=v1 -z --untracked-files=normal --ignore-submodules=none --ignored` in the tree; any entry not starting `!! ` -> `DIRTY` (532-540); then `git ls-files -s -z` entries with mode `160000` -> `SUBMODULE`; then `find_nested_repo` on each ignored entry -> `NESTED_REPO` (541-550).
- Stash: any stash on the same branch, or a branchless stash whose first parent equals the tree head (570-578).
- Process: any process cwd inside the tree, from `/proc` or `lsof -a -d cwd -F pcn` (337-394, 581-588).
- herdr: `herdr-api workspace list` (workspace `worktree.checkout_path` inside the tree, or no checkout_path and label equals folder name) and `herdr-api agent list` (`cwd` of any agent inside the tree) (396-453, 591-605). A herdr list that fails adds a note and its check is skipped; failed list is not re-asked in the run (`RunState.herdr_failures`).

Modes:
- List (default): `prune_worktrees(repo, False)` (734-740) prints plan, removes nothing, returns 0.
- `--apply`: for each removable tree `remove_one` (699-720) re-runs all checks on a fresh `World` (`recheck`, 687-696), then `git worktree remove <path>` (never `--force`), then `delete_branch` via `git update-ref -d refs/heads/<name> <tip>` after an ancestor check against the compare hash (797-810), then removes the `branch.<name>` config section (786). Totals line `removed N, freed ... bytes, kept N, failed N`; exit 1 when any failed (744-746).
- `--branches`: `prune_branches` (909-922) lists `for-each-ref --merged=<compare_hash> refs/heads/` minus the default branch and minus any branch held by a worktree entry or in a rebase/bisect in an existing worktree (`merged_free_branches` 872-879, `checked_out_branches` 858-869); with `--apply`, `delete_one_branch` (882-906) re-checks then deletes the same way.

Callers/cleanup invoking it: `rg --hidden` across `claude`, `install`, `scripts`, `herdr`, `tuios`, `zsh`, `.claude` finds no script, hook, timer, settings entry or install script that runs `herdr-worktree-prune`. Mentions are: `CLAUDE.md:46` (package description), `claude/.claude/scripts/gates/permission_question.py:14,62` (the word as an example of a feature name), `tests/scripts/test_herdr_worktree_prune.py`, `tests/scripts/test_staged_claim_gate.py`, and `docs/changes/` notes. Other worktree-removal code found: `zsh/.zshrc:369` (a shell function for `.claude/worktrees/<name>`: `git worktree remove`, then prompts and `git branch -d`/`-D` for `worktree-<name>`), `claude/.claude/skills/peer-review/SKILL.md:175` (`git worktree remove "${TMPDIR:-/tmp}/peer-review-<number>" --force`), `claude/.claude/scripts/review/full_check.py:584` (removes child worktrees via `git worktree remove`). `claude/.claude/settings.json:647-649` has `"worktree": {"baseRef": "fresh"}`. The only timers installed by `install/` that touch herdr are `install/herdr-wake-limited` (runs `herdr-wake-limited`, 2-minute interval); `install/daily-recap` and `install/weekly-recap` run claude recaps. The `SessionStart` hook at `claude/.claude/settings.json:487-` calls `ledger-hook session-start` (and a second entry) and no worktree cleanup (first entry read at lines 488-497). No "merge line" generator for worktree cleanup was found; the `pull_keep_index` merge-line reference is in `claude/.claude/CLAUDE.md:9` (push lines).

### 4. `herdr-phase-change`

File: `scripts/.local/bin/herdr-phase-change` (94 lines). Usage `herdr-phase-change [--timeout <seconds>] <agent> <prompt>` (line 5). `--timeout` default 30, whole seconds >= 1 (28, 34-39). Exactly one agent and one prompt (41-49); missing -> usage on stderr, exit 1 (55).

Target lookup: `agent_field` runs `herdr-api agent get "$target" | jq -r ".result.agent.<field> // empty"` (64-66). `$target` is passed straight to `herdr-api agent get` (an agent name or pane id per the usage text, line 6).

Sender identity (57-62): when the prompt does not start with `/`, it runs `herdr-api pane current | jq -r '.result.pane.pane_id // empty'`; empty -> stderr "cannot name the sending pane ...; sent nothing", exit 1. The prompt becomes `[from orchestrator pane <pane id>] <prompt>`. A slash-command prompt is sent unmarked. Nothing reads `HERDR_PANE_ID`, the sender's session id or session name in this script; `pane current` also returns `agent_session.value` and `label` (observed; `herdr-worktree:184-185` reads that session value).

Sequence:
1. `agent_status` must be `idle` or `done`, else stderr "is <status or not found>", exit 1 (68-72).
2. `old_session=agent_session.value`; empty -> exit 1 (74-76).
3. `herdr-api agent prompt "$target" "/clear"` (78).
4. Poll every 0.5 s until `agent_session.value` is non-empty and differs from `old_session`, bounded by the timeout; on expiry exit 1 "sent nothing more" (80-90).
5. `herdr-api agent wait "$target" --until idle --until "done" --timeout <ms>`; failure exit 1 (92-93).
6. `herdr-api agent prompt "$target" "$prompt"` (94) — its output and exit status are the script's.

Referenced by `claude/.claude/orchestration.md:36`. Test: `tests/scripts/test_herdr_phase_change.py`.

### 5. How `herdr agent list`, `herdr-api` and ListAgents identify agents

Observed from the running herdr (read-only calls in this session):
- `herdr-api agent list` -> `{"id":"cli:agent:list","result":{"agents":[...]}}`; each entry has exactly these keys: `agent`, `agent_session` (`{agent, kind, source, value}`), `agent_status`, `cwd`, `focused`, `foreground_cwd`, `pane_id`, `revision`, `state_change_seq`, `tab_id`, `terminal_id`, `terminal_title`, `terminal_title_stripped`, `workspace_id`. `agent_status` values seen: `idle`, `working`; others referenced in code: `done` (`herdr-phase-change:70`), and `blocked`, `unknown` (`scripts/.local/bin/herdr-fleet` header sort order: blocked > done > working > idle > unknown). There is no name/label key and no worktree-path key in an agent entry: the closest is `cwd` (and `foreground_cwd`).
- `herdr-api agent get <target>` returns an object with the same key set under `.result.agent` (`herdr-api agent get w53:p1`); a pane id is accepted as target.
- `herdr-api pane current` returns `.result.pane` with the agent keys plus `label` (e.g. `claude`), `scroll`; `pane list` entries carry `label` when set (`claude`, `review`, `editor` seen).
- `herdr-api workspace list` entries: `active_tab_id`, `agent_status`, `focused`, `label`, `number`, `pane_count`, `tab_count`, `workspace_id`, `worktree` (`checkout_path`, `is_linked_worktree`, `repo_key`, `repo_name`, `repo_root`).
- Not found, all exit 1 with JSON on stderr/stdout: `herdr-api agent get nonexistent-xyz` -> `{"error":{"code":"agent_not_found","message":"agent target nonexistent-xyz not found"},"id":"cli:agent:get"}`; `pane get w999:p9` -> `pane_not_found`; `workspace get w999` -> `workspace_not_found`. `herdr-worktree-watch:91` reads `.error.code`.
- `herdr-api` (`scripts/.local/bin/herdr-api`, 20 lines): under tuios (`TUIOS_SOCKET` set) sets `HERDR_SOCKET_PATH="$TUIOS_SOCKET.herdr"` and execs `<dirname TUIOS_SOCKET>/herdr/bin/herdr "$@"`; otherwise `exec herdr "$@"`. It adds no parsing and passes exit codes through.
- ListAgents is the Claude Code tool, not a herdr command. The repo's description: `claude/.claude/scripts/lib/session_registry.py:76-80` `session_display_name(session_id)` — "The name ListAgents shows for a live Claude Code session, read from the live registry rows", from `~/.claude/sessions/<pid>.json` (`name`, `sessionId`, `pid`, `cwd`; `live_session_rows` 41-55 keeps rows whose pid is alive). `claude/.claude/CLAUDE.md:11` says a lane brief carries this session's name read from ListAgents. `herdr-dev:114-115` names a forked session `--name <worktree folder name>`. `review_loop_calls.py:26` notes the ListAgents label of the loop's session.
- Agent identification in the scripts: pane id (`w53:p1` form) is the key `herdr-fleet` documents (`herdr agent read/focus` accept pane ids); `herdr-worktree-prune` identifies by `cwd` (`agent_cwds_from_json`, 421-425); `herdr-phase-change` by `agent get <name or pane id>`.

### 6. `hunk-review-pane`, pane/label variables, `herdr-dev` and `nvim-jump`

`scripts/.local/bin/hunk-review-pane` (107 lines, bash, `set -u` only, line 28):
- Sources `../lib/handoff-command.bash` via `readlink -f "$0"` (32).
- `--state-dir PANE_ID` prints `${XDG_RUNTIME_DIR:-$HOME/.cache}/hunk-review-pane/<PANE_ID with chars outside [A-Za-z0-9_.-] -> _>` and exits 0 (36-44; wrong arg count exit 2).
- Computes `base_ref`: on a branch other than `main`/`master`, merge-base of HEAD with `refs/remotes/origin/main` or `origin/master`, else empty (60-70). `hunk-untracked-flag` supplies an optional flag (48-53).
- Without `$HERDR_PANE_ID`: `exec hunk diff [base] --watch [flag] "$@"` (74-78).
- With `$HERDR_PANE_ID`: makes the state dir (80-81), exports `HUNK_REVIEW_HANDOFF=$dir/handoff` and `HUNK_REVIEW_PIDFILE=$dir/hunk.pid` (82-83), `trap 'rm -rf "$dir"' EXIT` (84), writes `root` = `git rev-parse --show-toplevel` or `pwd -P` (86-87). Loop (89-107): removes handoff/pid files, runs `hunk diff ... --watch`, if `handoff` file non-empty reads its first line as target (`nvim` or `lazygit` via `is_handoff_target`), runs it in a subshell with `cd "$repo_root"` via `exec_handoff_tool`, then loops back to hunk; otherwise exits with hunk's status.
- Variables used: `HERDR_PANE_ID`, `XDG_RUNTIME_DIR`, `HOME`, `HUNK_REVIEW_HANDOFF`, `HUNK_REVIEW_PIDFILE`. Header (19-21) says the pane id is fixed unless the pane moves workspaces.

`herdr-dev` sets the label: `herdr-api pane rename "$editor" review` (line 131) then `run "$editor" "hunk-review-pane"` (132). The claude pane is labelled `claude` (109), tab `code` (108), `console` tab created at 140. (Commented nvim variant at 129-130.)

`scripts/.local/bin/nvim-jump` look-up (lines 94-109, `open_nvim_in_review_pane`):
- requires `HERDR_ENV` (95);
- `tab=$(herdr-api pane current --current | jq -r '.result.pane.tab_id')` (97);
- `herdr-api pane list | jq` selecting `.tab_id == $tab and .label == "review"`, first `pane_id` (98-99);
- `state_dir=$(hunk-review-pane --state-dir "$review_pane")` (101), reads `root` (103) and requires the target file under it (104), reads `hunk.pid` and `kill -0` (105-106), writes `nvim` to `handoff` (107), `kill -TERM` the pid (108).
- Called only when no nvim socket owns the file (126-133); then `wait_for_owner` polls up to `NVIM_JUMP_WAIT_SECONDS` (default 10) in 0.2 s steps (112-124). Failure messages exit 1 (129-132).
- Other env: `NVIM_JUMP_SOCKET`, `XDG_RUNTIME_DIR`, `TMPDIR`, `USER` for socket discovery (35-42, 55).

Other readers of `HERDR_PANE_ID`: `scripts/.local/bin/clip-image:46-49`.

### 7. `pull_keep_index.py` flow

File: `claude/.claude/scripts/tools/pull_keep_index.py` (478 lines). Forms (docstring 1-2): `pull_keep_index.py <repo>` and `pull_keep_index.py --put-back <saved> <repo>`. Imports `script_utils` only from `lib/` (42-43). `main(arguments)` at 426.

Main path (`main`, 440-474):
1. `stopped_rebase_dir(repo)` — any `rebase-merge`/`rebase-apply` dir: exit 1 "nothing was pulled or set aside" with `rebase --continue`/`--abort` commands (442-444, 75-99).
2. `upstream_relation(repo)` (157-183): fetches the configured remote/merge ref; if the fetched `@{u}` tip is an ancestor of HEAD -> `ALREADY_HELD`; else if the tip is in `git rev-list --walk-reflogs refs/heads/<branch>` -> `REWRITTEN_LOCALLY`. Either prints one line and returns (exit 0) (446-449, 186-192).
3. `pull_target(repo)` (365-392): `@{u}` resolves -> `[]`; else detached -> `[]`; configured upstream whose remote lacks the ref -> `exit_upstream_gone` exit 1; no upstream and origin has `refs/heads/<branch>` -> `["origin", branch]`; origin lacks it -> `None`, prints "nothing to pull" and returns 0 (451-454).
4. `set_aside(repo)` (195-207): `git stash create`, then `git reset --hard --quiet`.
5. `git pull --rebase=merges --no-autostash [origin branch]` (457), via `subprocess.run` with inherited output.
6. If the pull failed and a rebase is stopped: `merge_in_place_of_rebase` (118-143) tries `git merge-tree --write-tree --quiet <orig-head> FETCH_HEAD`; if clean, `rebase --abort` then `merge --no-edit --quiet FETCH_HEAD`; else exit 1 with the stopped-rebase text plus the put-back recovery (461-466).
7. `put_back(repo, saved)` when `saved` is non-empty (468-469, 325-340): `git stash apply --index --quiet <saved>` with env `BUILT_PAGE_STASH=<saved>` (46, 330-331). On failure, stderr is passed through; if there are no conflicts and the staged-clash paths (`staged_clash_paths` 261-266: paths both the staged part, `saved^1..saved^2`, and the pull `saved^1..HEAD` changed) are all `merge=built-page` (`built_page_paths` 269-276) and the repo has `merge.built-page.driver` (`built_page_driver_configured` 279-283), `put_back_without_index` (286-300) applies without `--index`, restores the split, and `git add`s the pages; else `exit_unapplied` (303-322).
8. After the apply: pull failed -> `exit_if_upstream_gone` then exit 1 "git pull failed ...; the local changes are back in place" (470-472); else with a target, `set_upstream` writes `branch.<b>.remote` and `branch.<b>.merge` via `git config` (473-474, 411-423).

`--put-back <saved> <repo>` (427-436): verifies `<saved>^2` resolves (else exit 1 with the docstring), requires `git status --porcelain --untracked-files=no` to print nothing (else exit 1), then `put_back`. Any other argument shape: `sys.exit(__doc__)` (437-439).

Options: there are no flags other than the `--put-back` verb (`PUT_BACK_VERB`, 49). Constants: `BUILT_PAGE_STASH`, `BUILT_PAGE_DRIVER`, `FALLBACK_REMOTE = "origin"` (46-50).

Callers: `claude/.claude/CLAUDE.md:9` (rule that every push line runs it first), the hook text in `claude/.claude/scripts/gates/git_discipline_gate.py:363`, `docs/rule-anchors.md`. No script under `scripts/.local/bin/` calls it.

### 8. Existing scripts that print status or state information (invocation forms)

From `rg` of usage headers and reads of the files:
- `herdr-worktree-prune` — list mode, no args: lines per worktree to remove / kept with reason, totals (`scripts/.local/bin/herdr-worktree-prune`); `herdr-worktree-prune --branches` lists merged branches without a worktree.
- `nvim-jump --list` (live nvim instances and cwd, tab separated), `nvim-jump --where` (`file:line` under the cursor) — `scripts/.local/bin/nvim-jump:21-22,65-76`.
- `hunk-review-pane --state-dir PANE_ID` — prints the state dir path (`hunk-review-pane:40-44`).
- `herdr-fleet` — popup listing every agent pane by priority (`scripts/.local/bin/herdr-fleet`, bash, no args documented in header lines read).
- `herdr-api <herdr args>` e.g. `herdr-api pane current`, `agent list`, `workspace list`, `pane list`, `agent get <target>` — raw JSON (`scripts/.local/bin/herdr-api:4`).
- `herdr-balance`, `herdr-wake-limited [-h|--help]` (`herdr-wake-limited:5`; presses Enter on stuck panes, notifications).
- `claude-bg list`, `claude-bg logs` (`scripts/.local/bin/claude-bg`, usage block from line 10).
- `agent-cost` (`scripts/.local/bin/agent-cost:70` usage block; PEAK default, `--spend`).
- `theme-mode list` (`scripts/.local/bin/theme-mode:57` usage block; CLAUDE.md names `theme-mode list`).
- `branch-base [--head <branch>]` prints `<ref> <source>` (`claude/.claude/scripts/tools/branch-base:4`).
- `repo-name` (`claude/.claude/scripts/tools/repo-name`), `resolve-task-dir.sh [<path-or-ticket>]` (`tools/resolve-task-dir.sh:8`), `claude-doctor.sh` (`tools/claude-doctor.sh`), `rule-anchors.sh`.
- `ccusage-breakdown [start_date] [end_date]` (`ccusage-breakdown:3`), `hunk-theme-leaks`, `todo`, `achievement`, `bookmark`, `research` (usage blocks present; contents not read here).
- Review/code toolkit checkers: `questions_check.py check <questions-file>` (`tools/questions_check.py:3`), `plan_review_reports.py check <task-dir> <round>` (`:3`), `plan_review_shards.py cut <spec.md>` (`:3`), `criteria_dry_run.py <spec.md> [--repo DIR] [--skip N ...] [--timeout SECONDS]` (`:3`), `capture_packets.py store [<handback store dir>]` (`:4`).
- `herdr-worktree-watch` writes `still open` to its log (`herdr-worktree-watch:84`).

### 9. Test patterns under `tests/scripts/`

Files relevant here: `test_herdr_worktree.py`, `test_herdr_worktree_watch.py`, `test_herdr_worktree_prune.py`, `test_herdr_phase_change.py`, `test_herdr_wake_limited.py`, `test_pull_keep_index.py`, `test_detach.py`, `test_branch_base.py`, `test_toolkit_self_location.py`, plus helpers `stubs.py`, `toolkit_paths.py`, `isolated_state.py`, `in_process.py`, `receipt_repo.py`. No test file for `hunk-review-pane`, `nvim-jump` or `herdr-dev` by name (`rg --files`/`ls` of `tests/scripts` shows none; `herdr-dev` is exercised inside `test_herdr_worktree.py`: `HERDR_DEV` line 20).

External-command stubbing:
- `tests/scripts/stubs.py:4` `write_stub(path, body)` writes `#!/bin/bash\n<body>` and chmods 0755. Tests copy the script under test into a temp `bin_dir`, put stub `herdr`/`herdr-api`/`npm`/`pnpm`/etc. in it, and prepend it to `PATH` (`test_herdr_phase_change.py:60-80`; `test_herdr_worktree.py:42-64`).
- `test_herdr_phase_change.py:20` `STUB_HERDR_API`: shell stub whose state (status, session, prompts, flags like `no-current-pane`, `wait-fails`, `clear-delay`) lives in files under `$STATE_DIR`, switching on `"$1 $2"`.
- `test_herdr_worktree.py:51-62`: `herdr` stub records args to a file, runs the real `git worktree add`; `herdr-api`, `herdr-dev`, `herdr-worktree-watch` stubs `exit 0` by default; `CREATED_WORKSPACE`, `CLAUDE_PANE`, `SHELL_PANE` JSON constants (lines 21-23); `git(cwd, *args)` helper (line 26).
- `test_herdr_worktree_prune.py:34-56` `STUB_HERDR_API` with state files (`fail`, `garbage`, `fail-workspace`, `fail-agent`, `fail-from-call`, `dirty-on-call`, `workspaces-on-call`, `calls`); `STUB_GIT_FAILING_ONE_REMOVAL` and `STUB_GIT_MOVING_ONE_BRANCH` wrap real git (`$REAL_GIT`) to fail or race one call; real git against throwaway repos with a local bare `origin`; the script is also loaded as a module via `importlib.machinery` (imports at lines 9-10).
- `test_pull_keep_index.py`: real git only, with `GIT_ENV` (fixed author, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`; line 16-17); a bare `remote.git` plus clones; helper methods `git`, `clone`, `write`, `push_from_other_machine`, `run_script`, `saved_commit`, `mark_built_pages`, `status` (lines 28-76); runs `[sys.executable, SCRIPT, *args, repo]`.

Script path resolution:
- `tests/scripts/toolkit_paths.py:11-18`: `TREE_CLAUDE_DIR` (the `claude/.claude` of the tree the tests sit in), `CLAUDE_DIR` (overridden by `TOOLKIT_CLAUDE_DIR`), `SCRIPTS_DIR`, `TOOLS_DIR` etc. `test_pull_keep_index.py:15`: `SCRIPT = Path(os.environ.get("PULL_KEEP_INDEX_SCRIPT") or TOOLS_DIR / "pull_keep_index.py")`.
- Scripts under `scripts/.local/bin/` are resolved by `Path(__file__).resolve().parents[2] / "scripts" / ".local" / "bin"` (`test_herdr_phase_change.py:14`, `test_herdr_worktree.py:18-20`, `test_herdr_worktree_watch.py:14-15` with env override `HERDR_WORKTREE_WATCH`, `test_herdr_worktree_prune.py:24` with env `HERDR_WORKTREE_PRUNE`). Note `toolkit_paths.py` only covers `claude/.claude`, not `scripts/.local/bin`.

Runners:
- `tests/run.sh`: `set -euo pipefail`; unsets `CLAUDE_SKIP_HOOKS`; runs `tests/lint.sh`, `tests/duplicate_code.py`, snapshots the review-gate folder (`tests/review_gate_unchanged.py snapshot`), runs `tests/parallel_tests.py` under a temp `TMPDIR` and `SUITE_SLOT_DIR`, compares the gate state, and prints `FAILED: <steps>` and exits 1 when any step fails (lint exit 2 = missing ruff stops the run).
- `tests/lint.sh`: whole run is `ruff check --no-cache claude/.claude/scripts claude/.claude/skills tests/scripts tests/duplicate_code.py` plus a C901 report and a C901 gate on listed `/code` and review-flow files; with file arguments it lints only the given `.py` files (and `review/verify-log`, `review/verify-prep`). Exit 0/1/2.
- `tests/parallel_tests.py`: `main(file_names=())` at 233, `slot_folder()` at 119; `docs/toolkit-script-rules.md` says to run a test file as `python3 tests/parallel_tests.py <test file name>`.
- Scripts without `.py` (bash tools) are not linted by ruff (the ruff paths list `.py` files only).

### 10. Error handling, exit codes and `lib/` imports

Scripts under `scripts/.local/bin/` (as read):
- `herdr-worktree`: `set -euo pipefail`; error messages `herdr-worktree: ...` to stderr with `exit 1`; fzf Esc exits 0 (144); a failed push, failed install or failed `.python-version` link-less case warns and continues (245, 259); fork timeout exit 1 (280).
- `herdr-worktree-watch`: exits 1 for usage/invalid env/failed check; 0 for `still open`, tuios closed case, and after notification.
- `herdr-phase-change`: every failure `exit 1` with `herdr-phase-change: ...` on stderr; `-h` exit 0; the final `herdr-api agent prompt` status is the script's status.
- `herdr-dev`: `set -euo pipefail`; no-directory and no-workspace exit 1 (45, 54-55); best-effort wait (`|| true`, line 67).
- `herdr-worktree-prune`: `main` returns 0, 1 (`PruneError`, or any failed step on `--apply`), 2 (unknown argument); `Result` wraps subprocess so a missing binary becomes returncode 127 (195-201). Imports stdlib only (58-63).
- `hunk-review-pane`: `set -u` without `-e`; exits with hunk's status (99) or 1 for an unknown handoff target (104); `--state-dir` misuse exits 2.
- `nvim-jump`: `set -euo pipefail`; exits 0 jump, 1 no nvim/pane/dir, 2 bad args (header lines 28-29); sources `../lib/location-args.bash` (81).
- `herdr-api`: `set -euo pipefail`; `exec` so the herdr exit code passes through.

Scripts under `claude/.claude/scripts/tools/` (Python):
- `pull_keep_index.py`: failures are `sys.exit("pull_keep_index: <message>")` (a string exit gives status 1 and prints on stderr); success returns normally (0). Usage errors print `__doc__`. Child-process errors are returned, not raised (`run_in_repo`, 210-211, `capture_output=True`).
- Lib imports in `tools/*.py` (from `rg` of import lines): `pull_keep_index` -> `script_utils`; `ledger_deferred` -> `script_utils`; `sweep_scratchpads` -> `hook_input`, `session_registry`; `plan_review_shards` -> `plan_format`; `pipe_shell_check` -> `shell_command`, `shell_quoting`, `shell_statements`; `criteria_dry_run` -> `gate_env`, `plan_format`, `plan_verification` (code/), `script_utils`, `criteria_verdict.item_verdict`; `capture_packets` -> `coder_report`, `full_check`, `handback`, `handback_store`, `redact_text`, `script_utils`. Each adds `lib/` (and `code/`, `review/`) to `sys.path` at the top (e.g. `pull_keep_index.py:42`, `capture_packets.py:15`, `criteria_dry_run.py:24`).
- `claude/.claude/scripts/CLAUDE.md` rules stated for these scripts: no swallowed exceptions in hooks, gates choose fail-open/closed in a comment, state writes through `write_text_atomically` once per run.
- Bash scripts in `tools/` (`branch-base`, `notify`, `repo-name`, `resolve-task-dir.sh`, `claude-doctor.sh`, `rule-anchors.sh`, `hook-python`): `branch-base` uses `set -uo pipefail` and documents exits 0/1/2 (header 4-30).

### 11. `pull_keep_index.py`: what is saved, what stays in the tree, detection, pre-checks

- Saved: `git stash create` (line 197) — a commit holding tracked-file changes; it has parent 1 = HEAD and parent 2 = the index commit (the script reads `<saved>^1` as base, `<saved>^2` as index state, lines 223, 247, 264-265, 429). `stash create` with no `-u` option, so untracked files are not in it (the script passes no such option). The commit is not stored on any ref by the script (see Q12). Output empty -> clean tree -> `set_aside` returns `""` and no put-back runs (200-201, 468).
- After saving: `git reset --hard --quiet` (203), so the tree and index equal HEAD; untracked files are untouched by that reset and remain in place during the pull. The pull then runs on that tree (457).
- Dirty/staged detection: there is none in the main path; the `stash create` output is the only "is it clean" signal (197-201). Staged versus unstaged state is later derived from the saved commit's parents by `git diff --name-only --no-renames -z` (`listed_paths` 214-217) and a scratch-index build (`staged_tree` 220-236: `GIT_INDEX_FILE` in a `TemporaryDirectory`, `read-tree HEAD`, `apply --cached` of `diff --binary saved^1 saved^2`, `write-tree`). `--put-back` alone checks `git status --porcelain --untracked-files=no` (432-434).
- File lists recorded during the run: none are stored; `touched` is a set computed in memory in `restore_the_split` (248-251) from three diffs, and `staged_clash_paths` computes an in-memory intersection (261-266). No file is written by the script except `git config` entries via `set_upstream` and the temp scratch index.
- Checks before it starts: argument shape (427-439); stopped rebase (442-444); `upstream_relation` with a fetch (446-449); `pull_target` (451-454; ls-remote lookups, gone-upstream exit 1 before anything is set aside, per docstring 17-25). No check that the repo path is a git repo apart from the git failures those calls report.

### 12. Failure of the re-apply or `--put-back`

- Refs left behind: none are created by the script (rg for `update-ref`, `stash store`, `stash push`, `tag`, `branch -f` finds no calls; `refs/` appears only in `refs/heads/<branch>` lookups and config values). `docstring` line 14: "saved as a dangling stash commit, never on the shared stash stack". The saved commit is reachable only by its hash (printed in messages) and, until git garbage-collects it, from reflog-less storage; no named ref points at it. Test `test_pull_keep_index.py:` asserts `git stash list` is empty after a successful run (line ~89).
- Messages (all via `sys.exit`, status 1, stderr), each naming the saved commit with `saved_text` (`"The local changes are saved in <saved>"`, line 55):
  - `recovery_text` (68-72): `<saved_text>; on a clean tree, run: python3 <script realpath> --put-back <saved> <repo>` (shell-quoted).
  - No conflict but apply failed: `pull_keep_index: the local changes did not go back on cleanly. ` + recovery_text (308).
  - Conflicts (`exit_unapplied` 303-322): lists conflicted paths, says other files are back staged/unstaged, prints `git -C <repo> --literal-pathspecs reset -q <staged tree> -- <conflicted files>` (marks resolved with staged text), and for rebuilt pages `git ... add -- <pages>`, ending `The local changes are saved in <saved>.`
  - `restore_the_split` failures: "staged files could not be told apart" (245) or "could not restore the staged files" (257), each + recovery_text.
  - `put_back_without_index` stage failure: "could not stage the rebuilt pages ... To stage them, run: ..." + saved_text (299-300).
  - `set_aside` reset failure: "git reset failed ... " + recovery_text (206); `stash create` failure message has no saved commit (199).
  - Pull stops mid-rebase and no merge fallback: `stopped_rebase_text` + `put_back_text` ("Then put the local changes back." + recovery_text) (464-465); merge-fallback failures at 135-141.
  - Pull failed but put-back succeeded: "git pull failed in <repo>; the local changes are back in place." (472).
- `--put-back` itself uses the same `put_back` (435) and so the same messages as above; its own pre-check failures (not a saved commit; tracked changes) print the docstring and exit 1 (431, 434).
- Tests that pin these messages: `test_pull_keep_index.py:121,137,159,179,232,264,280,289,331,711,803` (names listed by `rg "def test_"`).

## Code References

- `scripts/.local/bin/herdr-worktree:52-280` — create worktree + workspace, install, layout, push, fork watcher launch.
- `scripts/.local/bin/herdr-worktree:182-187` — fork session read from `pane current`.
- `scripts/.local/bin/herdr-worktree:268-272` — watch log path and detached watcher start.
- `scripts/.local/bin/herdr-worktree-watch:83-126` — workspace check, recovery-step log, notification.
- `scripts/.local/bin/herdr-dev:104-168` — layout, labels, claude command, printed pane id.
- `scripts/.local/bin/herdr-worktree-prune:608` — `CHECKS` tuple; `:518` merged; `:530` dirty; `:699` `remove_one`; `:909` `prune_branches`; `:927` `main`.
- `scripts/.local/bin/herdr-phase-change:57-94` — sender mark, `/clear`, session wait, prompt.
- `scripts/.local/bin/herdr-api:14-20` — tuios vs herdr routing.
- `scripts/.local/bin/hunk-review-pane:36-107` — state dir, base ref, handoff loop.
- `scripts/.local/bin/nvim-jump:94-133` — review-pane lookup by `label == "review"`.
- `claude/.claude/scripts/tools/pull_keep_index.py:195-207,325-340,426-474` — set-aside, put-back, main.
- `claude/.claude/scripts/lib/session_registry.py:76-80` — ListAgents name source.
- `claude/.claude/scripts/lib/script_utils.py:297,592,597,609,614,422,292` — git/remote helpers used by `pull_keep_index`.
- `tests/scripts/stubs.py:4`, `tests/scripts/toolkit_paths.py:11-18`, `tests/run.sh`, `tests/lint.sh`, `tests/parallel_tests.py:119,233`.
- `claude/.claude/orchestration.md:35-36` — instructions invoking `herdr-worktree --fork` and `herdr-phase-change`.
- `claude/.claude/CLAUDE.md:9,11` — `pull_keep_index.py` push-line rule; ListAgents name in lane briefs.

## Patterns Found

- Each bash script prints `usage()` from its own header comments with `sed -n '2,/^$/s/^# \{0,1\}//p' "$0"` (`herdr-worktree:56`, `herdr-phase-change:26`); `nvim-jump` prints fixed lines (`:33`).
- All herdr access from scripts goes through `herdr-api`, with `export PATH="$HOME/.local/bin:$PATH"` at top (`herdr-worktree:53`, `herdr-phase-change:24`, `herdr-dev:42`).
- Error messages are `<script-name>: <text>` to stderr; Python tools use `sys.exit("<name>: <text>")`.
- Per-worktree files live under `git rev-parse --path-format=absolute --git-path <name>`.
- Tests copy the script into a temp bin dir with stubs first on PATH, drive stub state through files under a state dir, and use real git for git behaviour.
- Python tools add `lib/` to `sys.path` by computing it from `__file__` and import bare module names.
- The prune script is split into one function per condition (`check_*`) returning `Keep(code, text)` or `None`, and re-checks every condition before each removal.
- Recovery commands are printed shell-quoted (`shlex.join`, `printf %q`) so they paste back as written.

## Reuse Inventory

Scripts (stowed to `~/.local/bin/`):
- `herdr-api <herdr args...>` — `scripts/.local/bin/herdr-api:12` — runs herdr CLI against herdr or tuios.
- `detach <command> [args...]` — `scripts/.local/bin/detach:4` — runs a command in its own session (setsid or perl).
- `herdr-dev [dir] [ws] [claude_session] [start_prompt]` — `scripts/.local/bin/herdr-dev:5` — layout; prints claude pane id and command.
- `herdr-worktree-watch <ws> <worktree> <main> <pane> <parent session>` — `scripts/.local/bin/herdr-worktree-watch:5`.
- `hunk-review-pane --state-dir PANE_ID` — `scripts/.local/bin/hunk-review-pane:40` — path of a pane's state dir.
- `hunk-untracked-flag` — `scripts/.local/bin/hunk-untracked-flag` — optional hunk flag (output consumed at `hunk-review-pane:51`).
- `nvim-jump --list`, `--where` — `scripts/.local/bin/nvim-jump:65,70`.
- `hunk-notes` — `scripts/.local/bin/hunk-notes:10` — post notes to a hunk session.
- `herdr-fleet`, `herdr-balance`, `herdr-wake-limited`, `herdr-sessionizer`, `herdr-harpoon`, `herdr-project-open` — present in `scripts/.local/bin/`.
- `claude/.claude/scripts/tools/branch-base [--head <branch>]` — `tools/branch-base:4`; `tools/repo-name`; `tools/notify "Title" "Message"` (`tools/notify:5`); `tools/resolve-task-dir.sh [<path-or-ticket>]` (`:8`).

Libraries in `scripts/.local/lib/`: `handoff-command.bash` (`is_handoff_target`, `exec_handoff_tool`, used at `hunk-review-pane:104-106`), `location-args.bash` (`parse_location_args`, `resolve_location_files`, used at `nvim-jump:83-85`).

`claude/.claude/scripts/lib/script_utils.py`:
- `git_output(cwd, *args, timeout=None) → str | None` — `:297` — stdout of git, None on failure.
- `current_branch(cwd, timeout=None) → str | None` — `:592`.
- `remote_ref_state(repo, remote, ref) → (bool | None, str)` — `:597`.
- `branch_merge_ref(repo, branch) → str | None` — `:609`; `branch_remote(repo, branch) → str | None` — `:614`.
- `process_stderr_text(finished) → str` — `:422`; `escaped_glob(name) → str` — `:292`.
- `write_text_atomically(path, content)` — `:1239`; `state_file_path(state_dir, name, suffix)` — `:1279`; `read_jsonl(path)` — `:1323`; `read_ledger(args, wait_seconds=...)` — `:728`; `text_similarity(first, second)` — `:208`; `repo_name(cwd)` — `:~620`.
`claude/.claude/scripts/lib/session_registry.py`: `config_dir_override()` (`:14`), `sessions_dir()` (`:22`), `projects_dir()` (`:30`), `live_session_rows()` (`:38`), `other_live_session_in(folder, own_session_id)` (`:58`), `holder_label(row)` (`:70`), `session_display_name(session_id)` (`:76`).
Other lib modules named in `claude/.claude/scripts/CLAUDE.md` owner list: `file_lock.py`, `process_group.py` (`pid_is_alive`), `shell_command.py`, `git_commit_calls.py`, `toml_file.py` (`read_toml`), `import_guard.py` (`guard`).

Test helpers: `write_stub(path, body)` — `tests/scripts/stubs.py:4`; `TOOLS_DIR`, `SCRIPTS_DIR`, `LIB_DIR`, `GATES_DIR`, `CLAUDE_DIR` — `tests/scripts/toolkit_paths.py:11-18`; `git(cwd, *args)` — `tests/scripts/test_herdr_worktree.py:26`; `PullKeepIndexTest` helpers `git/clone/write/push_from_other_machine/run_script/mark_built_pages` — `tests/scripts/test_pull_keep_index.py:28-70`; `tests/scripts/fake_ledger.py`, `isolated_state.py`, `in_process.py`, `receipt_repo.py` (present; not read).

## Dormant Scaffolding

- `herdr-worktree-prune`: `Worktree.lock_reason` is written (`:279`) and read once (`:502`); `Worktree.prunable` is written (`:281`) and read at `:494` and `:865`. No fields found written but never read in the parts read. `HERDR_TIMEOUT_SECONDS`, `LSOF_TIMEOUT_SECONDS`, `FETCH_TIMEOUT_SECONDS` are used.
- `herdr-dev:129-130` — commented-out nvim editor lines (documented in the header at 22-23 and 126-127).
- `herdr-phase-change` does not read `HERDR_PANE_ID` and does not use the sender's session id/name; `pane current` is the sole sender lookup (`:58`).
- `hunk-review-pane` sets `HUNK_REVIEW_PIDFILE`, which the extension (`hunk/.config/hunk/extensions/claude-review.ts`) writes; the shell script reads the file only to `rm` it (`:90,96`); `nvim-jump` reads it (`:105`).
- `pull_keep_index.py`: `BUILT_PAGE_STASH` is exported to `git stash apply` (`:46,330`) and read by an external script (`~/agent-evals/bin/merge_built_page.py`, per the comment at line 45; not in this repo).
- `herdr-worktree` `--base` only affects the base ref; no state records it.
- No hook, timer, install script or settings entry invokes `herdr-worktree-prune` (see Q3).
