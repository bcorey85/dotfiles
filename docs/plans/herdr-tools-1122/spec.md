# herdr lane tooling: eight queued fixes

> Ticket: ./00-ticket.md (eight queue items from ~/agent-evals/queue/)
> Research: ./02-research.md (goal-blind, produced before design began)
> Decisions: ./03-decisions.md (the design-resolution ledger)
> Date: 2026-11-22

<!-- Source precedence: on anything concrete, THIS file wins over the ledger (which records why, not what). A disagreement between them is a spec bug — report it. -->

## Summary

A lane started with `herdr-worktree --fork` writes a durable lane file; `herdr-lane-resume <name>` reopens a dead lane from it and `--close <name>` removes it and prunes merged lane worktrees; `lane-status` reports memory, scratch space and lanes that are not working. `herdr-phase-change` takes a ListAgents session name or a worktree path, appends the report-to session to the prompt, and keeps the lane file current. `hunk-review-pane` labels its own pane `review`. `pull_keep_index.py` prints `--help`, keeps a named ref for the saved changes, rebuilds clashing built pages through the configured merge driver, and never sets another live session's edits aside in a shared checkout.

## Phase Status

<!-- Hoisted from below so the first screen answers "where are the agents?". The one section that changes after writing (/code ticks it) — source of truth for "which phase is next". Do not move it back down. -->

- [x] Phase 0: Contracts — lane file grammar, `lanes.py` CLI, `row_for_name` — frozen at plan approval (risk: high)
- [x] Phase 1: Walking skeleton — a fork writes the lane file, the watcher fills the session id, phase-change keeps it current (risk: low)
- [x] Phase 2: hunk-review-pane labels its own pane (risk: low)
- [x] Phase 3: pull_keep_index `--help` and the named save ref (risk: high)
- [x] Phase 4: pull_keep_index built-page put-back through the merge driver (risk: high)
- [x] Phase 5: pull_keep_index in a shared checkout (risk: high)
- [x] Phase 6: herdr-phase-change resolves a session name or a worktree path (risk: low)
- [x] Phase 7: herdr-phase-change names the report-to session (risk: low)
- [x] Phase 8: herdr-dev resume mode and herdr-lane-resume (risk: high)
- [ ] Phase 9: lane-status (risk: low)
- [ ] Phase 10: prune keeps open lanes; `--close` runs it (risk: high)
- [ ] Phase 11: Close-out — change pages, propagation sweep, full suite (risk: low)
- [ ] Phase 12: Close pass — /close-branch parallel review, one fix, fix-diff gate, recap (risk: high)

## Decisions

- P3: round-1 review rulings — `--close` closes the workspace first and refuses on a working agent; watcher noise on a deliberate close accepted; ban grep narrowed to `put_back_without_index` with `--hidden`; `sender` prints JSON on failure; lock timeout from `PULL_KEEP_INDEX_LOCK_SECONDS`; `--put-back <hash>` gets a ref before the apply.

<!-- One line per block in 03-decisions.md's ## Resolved: `N. [Topic] — [Choice]`, plus `Trade-off: …` only where it changes code. -->

- D1/Q1. Lane file — `${XDG_STATE_HOME:-$HOME/.local/state}/herdr-lanes/<name>.json`, one object per lane, one Python owner `lib/lane_entries.py`, CLI `tools/lanes.py`; bash never parses it. Trade-off: a removed worktree leaves its entry until `--close`.
- D2. Resume — new `herdr-lane-resume <name>` reopens the workspace and runs `herdr-dev --resume`, which types `claude --resume <id> --name <name>` with the brief and no `--fork-session`; `--close <name>` removes the entry.
- D3. Session id — herdr-worktree writes the entry with an empty `session_id` at fork start; the watcher fills it; herdr-phase-change writes the post-`/clear` id and the phase prompt for the lane whose worktree holds the target's cwd. Trade-off: a hand `/clear` leaves a stale id.
- D4/Q6. lane-status — matches agents by cwd inside the worktree; prints `no agent`, any non-`working` status, `worktree gone`, low memory, low scratch free space and scratch usage over a cap; exit 0 nothing, 1 printed, 2 bad file or failed tool.
- D5. Target resolution — `tools/session_pane.py resolve <arg>`: an existing directory → the one claude agent whose cwd is inside it; a live registry `name` → its sessionId → the agent with that `agent_session.value`; else as given.
- D6/Q7. Report-to — herdr-phase-change appends ` [report to session <sender>]` to every prompt, slash prompts included; no sender name → exit 1, nothing sent; no skill edit. Trade-off: `/code` sees the marker as a run note until the code-skill lane strips it.
- D7/Q5. Prune — `herdr-lane-resume --close` runs `herdr-worktree-prune --apply` in the lane's main checkout; prune keeps a tree inside an open lane's worktree (`open lane`), fail-closed when the lane list cannot be read. Current, locked, stashed, held and squash-merged trees stay.
- D8/Q8. Shared checkout — another live session in the repo (`other_live_session_in`, a missing `CLAUDE_CODE_SESSION_ID` counts as shared) plus a dirty tree: not ahead → `git merge --ff-only`, refusing and naming the overwritten paths on failure; diverged → refuse naming the dirty files and the way out; nothing set aside either way. The run holds `<common dir>/pull-keep-index.lock`.
- D9. Save ref — `refs/pull-keep-index/<UTC stamp>-<saved[:8]>` right after `stash create`, named in every message, deleted only by its own successful put-back; older refs listed, never deleted (P1.3).
- D10. Built pages — when a staged clash set holds a built page and the driver is configured: apply `saved^1..saved^2` minus pages `--index --3way`, `write-tree`, apply `saved^2..saved` minus pages `--3way`, `read-tree` the saved index, run the configured driver per page with `%O %A %B %P` substituted and `BUILT_PAGE_STASH=<saved>`, `git add` the pages. One function serves the run and `--put-back`.
- D11/Q9. hunk-review-pane — `herdr-api pane rename "$HERDR_PANE_ID" review` at start; a failed rename warns and continues; the label stays on exit.
- Q2. Terms — "lane", "lane file", "lane list"; no glossary entry.
- Q3. Only `--fork` writes a lane entry. Q4. The lane file holds the latest prompt; resume sends it.
- P2. Walk rulings 1–6 by agent-evals-c3 (ledger `### P2`): D1 and D7 stand for the ticket wording; a failed lane-file write warns with path and error and the fork starts; no sender → send nothing, exit 1 with the reason; `--close` on a gone folder removes the entry and says so.
- P1. Architect deviations 1–6 accepted (ledger `### P1`): CLI name `lanes.py`, one `set-session` verb, no ref cleanup, `write-tree`/`read-tree` around the unstaged apply, change-file root in this worktree, driver through `sh -c`.

## Approaches Considered and Not Taken

- A SessionStart hook entry or a timer for the prune: a new hook process, and it would prune every repo a session starts in, the work machine included.
- herdr agent names as the lane or ListAgents identity: `[a-z][a-z0-9_-]{0,31}`, cleared on exit, so a dead lane has none.
- A jq reader of `~/.claude/sessions` in bash: a second copy of the `session_registry` fact that misses `CLAUDE_CONFIG_DIR`.
- `git stash push` or `stash store` to name the save commit: writes the stash stack other sessions pop.
- Hard-coding `build_changes.py` in pull_keep_index: the driver owns which builder makes each page.
- Picking the newest transcript at resume time: wrong with two sessions in one tree.
- Lane file in the scratchpad, `/tmp` or the worktree's git dir: wiped by the reboot or the `git worktree remove` that caused the incident.

## Constraints

- Four platforms (WSL, Ubuntu, macOS, Arch), bash 3.2 on macOS, Python 3.10, git 2.34 on Ubuntu 22.04: `merge-tree --write-tree` and `git replay` are unavailable; `apply --3way`, `write-tree`, `read-tree`, `merge --ff-only`, `update-ref` are (exercised: research §7).
- Package installs only through apt, brew, pacman. No new dependency; `jq` is already required by the herdr scripts.
- This lane never edits `claude/.claude/settings.json`, any CLAUDE.md, `claude/.claude/orchestration.md` or a skill file. Lines for those go to the orchestrating session.
- `docs/toolkit-script-rules.md` and `claude/.claude/scripts/CLAUDE.md` bind every file under `claude/.claude/scripts/`: snake_case, one grammar with loud failures and a `check` verb, owners (`session_registry`, `file_lock`, `process_group`, `script_utils.write_text_atomically`, `shell_command`), tests in `tests/scripts/test_<script>.py` with paths from `tests/scripts/toolkit_paths.py`, run through `python3 tests/parallel_tests.py <file>`.
- `scripts/.local/bin/herdr-worktree-prune` is 949 lines; the 1000-line rule allows the ~30-line keep and nothing more. Over 999 lines the coder stops and reports.
- Bash scripts reach the Python tools through `${HERDR_LANES_CLI:-$HOME/.claude/scripts/tools/lanes.py}` and `${HERDR_SESSION_PANE:-$HOME/.claude/scripts/tools/session_pane.py}`, so tests point them at the tree copies.
- `~/.claude/sessions/<pid>.json` rows carry `name`, `nameSource`, `sessionId`, `cwd`; the registry `sessionId` equals herdr's `agent_session.value`; Bash tool env holds `CLAUDE_CODE_SESSION_ID` (exercised: research §4).
- `/tmp` is tmpfs with a per-user quota that `df` cannot see; `du -sk` of the scratch root against a cap is the usable reading (exercised: research §3).
- `session_registry.other_live_session_in(folder, None)` matches the caller's own row, so a missing session id reads as shared with no new code (exercised by the architect).
- `git apply --3way` stages what it applies (exercised by the architect in a scratch repo).
- Every toolkit edit gets a change file: `python3 ~/agent-evals/bin/build_changes.py new "<title>" --by claude-code/<model id> --root /home/brandon/dotfiles-herdr-tools-nov22/docs/changes`, then the build with the same `--root`.

## External Contracts

- herdr 0.8.2 CLI (exercised: research §1, §12): `herdr worktree open [--workspace ID | --cwd PATH] (--path PATH | --branch NAME) [--label TEXT] [--focus]` (result `.result.workspace.workspace_id`); `herdr agent get <name|pane>`; `herdr agent rename`; `herdr pane rename <pane_id> <label>|--clear`; `herdr-api agent list` entries with `pane_id`, `cwd`, `agent`, `agent_status` (idle|working|done|blocked|unknown), `agent_session.value`, optional `name`; errors as `.error.code` `agent_not_found|pane_not_found|workspace_not_found`. A changed field name breaks resolution and lane-status matching; both exit 2 naming the call when the list cannot be read.
- `herdr-api` picks the tuios shim when `TUIOS_SOCKET` is set (declared-only: CLAUDE.md). `herdr-lane-resume` under tuios uses `herdr-api workspace create --cwd <wt> --label <name> --focus`. A shim lacking `pane rename` makes hunk-review-pane warn and continue.
- Claude Code: `claude --resume <id> --name <name> -- "<prompt>"` resumes without forking; `--fork-session` forks (exercised: herdr-dev today). The session registry row format above (exercised).
- Built-page merge driver `merge.built-page.driver = /usr/bin/python3 /home/brandon/agent-evals/bin/merge_built_page.py %O %A %B %P`, cwd at the work tree root, honours `BUILT_PAGE_STASH` and checks the three files hold the blobs of the stash parent, HEAD and the stash (declared-only from reading the driver; Phase 4 exercises it once by hand against a clone of this worktree). `.gitattributes` marks the six pages `merge=built-page`.
- git plumbing used in `pull_keep_index.py`: `stash create`, `update-ref`, `apply --index --3way`, `write-tree`, `read-tree`, `merge --ff-only`, `rev-list --count` (exercised on git 2.34 and 2.4x).
- Internal: `lib/session_registry.py` owns session rows (gains `row_for_name`); `lib/file_lock.py` owns cross-process locks; `lib/script_utils.py` owns atomic writes. No second copy of any of them.

## Approach

- Area 1, lane state: `lib/lane_entries.py` (grammar) + `tools/lanes.py` (CLI) are written first and frozen; herdr-worktree, herdr-worktree-watch, herdr-phase-change, herdr-lane-resume, lane-status and the prune are callers.
- Area 2, session-to-pane join: `tools/session_pane.py` (`resolve`, `sender`) joins the registry to the herdr agent list; herdr-phase-change and herdr-worktree call it.
- Area 3, pull_keep_index: three phases on one file, each with the real-git fixture in `tests/scripts/test_pull_keep_index.py`.
- Area 4, pane label and prune: one-line behaviour changes with a stub-herdr test each.
- Patterns: JSON out on stdout, errors on stderr, exit 0/1/2; `write_text_atomically` under `file_lock.hold_exclusive`; `LaneFileError(path, field, expected)` → `lanes: <file>: field <f>: expected <form>` exit 2; stub binaries through `tests/scripts/stubs.py write_stub`; bash scripts `set -euo pipefail` with a header `usage()`.

## Dependencies

- External: none new.
- Internal: `script_utils` (`write_text_atomically`, `git_output`), `file_lock.hold_exclusive`, `session_registry` (`live_session_rows`, `session_display_name`, `other_live_session_in`, `holder_label`), `hook_input.claude_code_temp_root`, `process_group.pid_is_alive`; in `pull_keep_index.py`: `listed_paths`, `built_page_paths`, `built_page_driver_configured`, `page_stage_arguments`, `exit_unapplied`, `recovery_text`, `saved_text`; in the prune: `World`, `Keep`, `CANNOT_CHECK`, `inside`, `real`, `remove_one`.

## Implementation Plan

### Acceptance Criteria

- **Criteria file**: `docs/plans/herdr-tools-1122/acceptance-criteria.md`

### Size estimate

About 1,900 changed lines, roughly 45% tests. Report the real diff at hand-over; stop and report to the orchestrating session over 3,800.

## Phase 0: Contracts — lane file grammar, `lanes.py` CLI, `row_for_name`

### Overview

The one grammar for the lane file and the CLI every bash caller uses, plus the registry lookup by name. Frozen at approval: a later field or verb is a Plan Deviation.

### Changes Required:

#### 1. Lane entry owner

**File**: `claude/.claude/scripts/lib/lane_entries.py` (new)
**Changes**: `lanes_dir()` = `${XDG_STATE_HOME:-$HOME/.local/state}/herdr-lanes`; `LaneFileError(path, field, expected)`; `read_entry(file)` (the one grammar); `all_entries()` sorted by `name`; `entry(name)`; `entry_containing(path)` (realpath + `script_utils.path_is_under`); `add_entry(name, worktree, main_checkout, branch, brief, reports_to)`; `set_session(name, session_id, brief=None)` returning whether anything changed; `remove_entry(name)` returning the removed entry. Every write: `file_lock.hold_exclusive(<dir>/lanes.lock, 10)` (the one lock name; the 10 s timeout is fixed, so the lock test in §4 takes up to 10 s, accepted), read, validate, `write_text_atomically`. Fields and rules:

| field | type | rule |
|---|---|---|
| `name` | str | `^[A-Za-z0-9][A-Za-z0-9._-]*$`, equals the file stem |
| `worktree` | str | absolute path |
| `main_checkout` | str | absolute path |
| `branch` | str | non-empty |
| `brief` | str | non-empty; the latest prompt sent |
| `session_id` | str | `""` until filled |
| `reports_to` | str | ListAgents name of the starting session, or `""` |
| `started_at` | str | ISO-8601 with offset, seconds |

Unknown key, missing key, wrong type, stem mismatch or invalid JSON raise `LaneFileError`. `add_entry` raises when an entry exists whose `worktree` folder exists; it replaces one whose folder is gone.

#### 2. Lane CLI

**File**: `claude/.claude/scripts/tools/lanes.py` (new)
**Changes**: argparse verbs, JSON on stdout: `add --name N --worktree W --main-checkout M --branch B [--reports-to R]` (brief on stdin; exit 1 when a live entry exists); `set-session N ID [--brief-stdin]` (prints `{"changed": true|false}`; exit 1 no entry); `remove N` (prints the removed entry; exit 1 no entry); `get N` → `{"entry": {...}|null}`; `get --containing PATH`; `list` → `{"lanes": [...]}`; `check [FILE...]` (default all; exit 2 on the first bad file). `LaneFileError` → stderr `lanes: <file>: field <f>: expected <form>`, exit 2; `file_lock.LockTimeoutError` → stderr `lanes: lock <path> held for <n>s`, exit 2. `sys.path` from `pathlib.Path(__file__).resolve()`.

#### 3. Registry lookup by name

**File**: `claude/.claude/scripts/lib/session_registry.py`
**Changes**: `row_for_name(name)`: the first live row (file order, as `live_session_rows`) whose `name == name`, else `None`. Docstring updated.

#### 4. Tests

**Files**: `tests/scripts/test_lane_entries.py` (new), `tests/scripts/test_lanes.py` (new), `tests/scripts/test_session_registry.py`
**Changes**: `test_lane_entries.py` covers the lib under a temp `XDG_STATE_HOME`: add/get/list sorted/remove; set-session with and without a brief, and the `changed` flag; stale-entry replace when the worktree folder is gone and refusal when it exists; `get --containing` on a nested path and an outside path; each bad shape (missing key, extra key, wrong type, stem mismatch, invalid JSON) raises `LaneFileError` naming file and field. `test_lanes.py` runs the CLI as a subprocess: every verb's JSON, exit 2 on each bad shape with file and field on stderr, `check` over a folder with one bad file, and exit 2 naming the lock when a Python child holds `<dir>/lanes.lock` through `file_lock.hold_exclusive` (the same file §1 names). `row_for_name`: found, dead pid skipped, absent.

Change file: "herdr lane file grammar and lanes CLI" (by the coder's model id, root `/home/brandon/dotfiles-herdr-tools-nov22/docs/changes`).

### Success Criteria

A lane file with every field round-trips through the CLI; every malformed shape is refused with file and field.

#### Automated Verification

- [ ] `python3 tests/parallel_tests.py test_lane_entries.py` (RED before: module missing)
- [ ] `python3 tests/parallel_tests.py test_lanes.py` (RED before: script missing)
- [ ] `python3 tests/parallel_tests.py test_session_registry.py`
- [ ] `bash tests/lint.sh claude/.claude/scripts/lib/lane_entries.py claude/.claude/scripts/tools/lanes.py claude/.claude/scripts/lib/session_registry.py`

#### Manual Verification

N/A (infra-only: a library and its CLI, fully covered above).

## Phase 1: Walking skeleton — a fork writes the lane file, the watcher fills the session id, phase-change keeps it current

### Overview

The thinnest end-to-end path through the Phase 0 contract: `herdr-worktree --fork` writes an entry, `herdr-worktree-watch` fills `session_id`, `herdr-phase-change` updates `session_id` and `brief` after a phase change. `/code` stops after this phase for calibration.

### Changes Required:

#### 1. Sender name

**File**: `claude/.claude/scripts/tools/session_pane.py` (new; the `resolve` verb comes in Phase 6)
**Changes**: `sender` finds the name from `CLAUDE_CODE_SESSION_ID`, else from `herdr-api pane current` → `agent_session.value`, each through `session_registry.session_display_name`. Found → prints `{"name": "..."}`, exit 0. Otherwise it prints `{"name": null, "reason": "<why>"}` on stdout: exit 1 when neither source gives a name, exit 2 when the herdr-api call fails (the reason names the call). Bash callers read `.name` and `.reason` and never parse stderr.

#### 2. Entry at fork start

**File**: `scripts/.local/bin/herdr-worktree`
**Changes**: next to `bin_dir`, define `lanes_cli=${HERDR_LANES_CLI:-$HOME/.claude/scripts/tools/lanes.py}` and `session_pane=${HERDR_SESSION_PANE:-$HOME/.claude/scripts/tools/session_pane.py}`. Only with `--fork`, after the workspace id is known and before herdr-dev: `reports_to=$(python3 "$session_pane" sender 2>/dev/null | jq -r '.name // empty' 2>/dev/null) || reports_to=""`; the brief (from `--prompt-file` or the argument, the variable the script already loads) piped to `python3 "$lanes_cli" add --name "$label" --worktree "$worktree" --main-checkout "$main_checkout" --branch "$branch" --reports-to "$reports_to"`. A failed add warns on stderr "herdr-worktree: lane entry not written at <path>: <error>; herdr-lane-resume will not know this lane" and the fork still starts (P2.4). Header lines 31-47 describe the lane file; the recovery text names `herdr-lane-resume <name>` (the script lands in Phase 8).

#### 3. Session id from the watcher

**File**: `scripts/.local/bin/herdr-worktree-watch`
**Changes**: define `lanes_cli` as herdr-worktree does, and move the `label` assignment (today line 102) above the session-id read (around line 75) so both steps can use it. Once the fork's session id is read: `lane_entry=$(python3 "$lanes_cli" get "$label" 2>/dev/null | jq -r '.entry // empty' 2>/dev/null) || lane_entry=""`; only when `lane_entry` is non-empty run `python3 "$lanes_cli" set-session "$label" "$session"`, and only its failure writes one log line `lane <label>: session id not stored: <stderr>`. With no entry nothing is run and nothing is logged, so every existing watcher test (no entry) keeps its exact log text. When the workspace is gone, read the lane first: `lane_session=$(python3 "$lanes_cli" get "$label" 2>/dev/null | jq -r '.entry.session_id // empty' 2>/dev/null) || lane_session=""`. `lane_session` non-empty → the log gets exactly two lines, `workspace <ws> closed. Recovery steps:` and `1. herdr-lane-resume <label>`, under herdr and tuios alike (herdr-lane-resume handles tuios itself). `lane_session` empty → today's lines stay exactly as they are, with or without a fork session id, tuios focus step included; "empty" covers no entry, a failed `add` (P2.4) and a failed `set-session`. On a deliberate `herdr-lane-resume --close`, the watcher still writes its two lines and posts one notification; accepted as noise (lane ruling, 03-decisions.md).

#### 4. Phase change writes the lane

**File**: `scripts/.local/bin/herdr-phase-change`
**Changes**: right after `export PATH=...`, define `lanes_cli` and `session_pane` as herdr-worktree does; Phases 6 and 7 use these two variables, never the inline `${...:-...}` form. After the final prompt succeeds: `cwd` from `agent get`; when `cwd` is empty (the existing stub returns none) the step ends with no lookup, since `get --containing ""` would realpath to the caller's cwd; otherwise `lane=$(python3 "$lanes_cli" get --containing "$cwd" | jq -r '.entry.name // empty') || lane=""`; when set, the sent prompt piped to `python3 "$lanes_cli" set-session "$lane" "$new_session" --brief-stdin || echo "herdr-phase-change: lane $lane not updated" >&2`. The stored brief is the sent text as a whole, `[from orchestrator pane <id>]` prefix and report-to marker included (accepted: a resume replays the prefix). A failure warns and exits 0; a comment says the step is fail-open because the prompt already went out.

#### 5. Tests

**Files**: `tests/scripts/test_herdr_worktree.py`, `tests/scripts/test_herdr_worktree_watch.py`, `tests/scripts/test_herdr_phase_change.py`, `tests/scripts/test_session_pane.py` (new)
**Changes**: tests set `HERDR_LANES_CLI` and `HERDR_SESSION_PANE` to the tree copies and `XDG_STATE_HOME` to a temp folder. Fork run → the entry holds worktree, branch, brief, `session_id == ""`, `reports_to`; a non-fork run writes no entry. Watcher with an entry → `set-session` filled `s1` and `recovery_lines` equals `["workspace wX closed. Recovery steps:", "1. herdr-lane-resume repo-fork"]` under herdr and under `TUIOS_SOCKET` (the test at line 263); with no entry (`HERDR_LANES_CLI` at a missing file) the herdr and tuios outputs equal today's three lines and the log text is unchanged (the exact-log assertions at lines 94, 105 and 261 stay as they are); with an entry whose `session_id` is empty (a stub lanes CLI, a Python file written with `write_text` and not `write_stub`, since every caller runs it through `python3`; it prints such an entry for `get` and exits 1 for `set-session`) the output is today's lines plus the one `session id not stored` line. Phase change with an entry whose worktree is `$STATE_DIR/wt` → `session_id == "s2"` and `brief` equals the sent text; an agent outside any lane writes nothing. `sender` from env, from the `pane current` fallback, and none → exit 1.

Change file: "herdr lanes keep their brief and session id in a durable lane file".

### Success Criteria

A forked lane has a lane file with its brief, worktree, branch and session id before the user touches anything, and a phase change keeps the file current.

#### Automated Verification

- [x] `python3 tests/parallel_tests.py test_herdr_worktree.py` (RED before: no entry)
- [x] `python3 tests/parallel_tests.py test_herdr_worktree_watch.py` (RED before: old recovery text)
- [x] `python3 tests/parallel_tests.py test_herdr_phase_change.py` (RED before: lane not updated)
- [x] `python3 tests/parallel_tests.py test_session_pane.py`
- [x] `bash tests/lint.sh claude/.claude/scripts/tools/session_pane.py`

#### Manual Verification

- **Agent-run**, inside herdr, from a scratch clone of this worktree at `S/clone` under the scratchpad (Phases 6, 7, 8, 9 and 10 reuse it): in one Bash call, `export HERDR_LANES_CLI=/home/brandon/dotfiles-herdr-tools-nov22/claude/.claude/scripts/tools/lanes.py HERDR_SESSION_PANE=/home/brandon/dotfiles-herdr-tools-nov22/claude/.claude/scripts/tools/session_pane.py` and then `/home/brandon/dotfiles-herdr-tools-nov22/scripts/.local/bin/herdr-worktree --fork --prompt-file <brief> probe/lane-file` (herdr-worktree runs herdr-dev, detach and the watcher from its own `$bin_dir`, so those are the worktree copies too; the exported variables reach the detached watcher through the environment). The brief is a no-op: "Reply ok and stop. Edit nothing, commit nothing." Every later manual check that reads `$HERDR_LANES_CLI` exports both variables again in its own Bash call, since Bash calls keep no shell state. Then `python3 "$HERDR_LANES_CLI" get <worktree basename>`: the entry shows the brief and, once the watcher has read the fork's id, a non-empty `session_id`. Keep the probe lane open: Phases 6 to 9 use it, and Phase 10's check runs `--close` on it.

## Phase 2: hunk-review-pane labels its own pane

### Changes Required:

#### 1. Rename at start

**File**: `scripts/.local/bin/hunk-review-pane`
**Changes**: after the `HERDR_PANE_ID` guard (lines 73-78), before `mkdir`: `herdr-api pane rename "$HERDR_PANE_ID" review >/dev/null 2>&1 || echo "hunk-review-pane: could not label pane $HERDR_PANE_ID review; nvim-jump will not find it" >&2`. No PATH change: the header line 23 keeps env as the caller's job. One header line.

#### 2. Rule note

**File**: `.claude/rules/hunk.md`
**Changes**: one clause: the pane labels itself `review` at start.

#### 3. Test

**File**: `tests/scripts/test_hunk_review_pane.py` (new; script path from env `HUNK_REVIEW_PANE`, default the tree copy)
**Changes**: `setUp` prepends the stub bin folder to `PATH`, which is what makes the stub `herdr-api` win over `~/.local/bin/herdr-api` (the script sets no PATH of its own); it also sets `HOME` to a temp folder (as `test_herdr_phase_change.py:75` does) so no user config is read; stubs `herdr-api` (appends `$*` to a calls file) and `hunk` (exit 0, no handoff), inside a temp git repo. Unlabeled pane `HERDR_PANE_ID=wT:p1` → the calls file holds `pane rename wT:p1 review`; rename failure → hunk still runs and stderr names the pane; no `HERDR_PANE_ID` → no herdr-api call.

Change file: "hunk-review-pane labels its own herdr pane review".

### Success Criteria

A hand-started review pane is found by nvim-jump without a hand rename.

#### Automated Verification

- [x] `python3 tests/parallel_tests.py test_hunk_review_pane.py` (RED before: no rename call)

#### Manual Verification

- In herdr, open a fresh pane inside a git repo with an unstaged diff and run `/home/brandon/dotfiles-herdr-tools-nov22/scripts/.local/bin/hunk-review-pane` by path (never `hw`, which goes through the stowed master copy). From another pane, `herdr-api pane list | jq '.result.panes[] | {pane_id, label}'` shows that pane labeled `review`.

## Phase 3: pull_keep_index `--help` and the named save ref

### Changes Required:

#### 1. Help and ref

**File**: `claude/.claude/scripts/tools/pull_keep_index.py`
**Changes**: `main` prints `__doc__` and exits 0 for `-h`/`--help`. `REF_PREFIX = "refs/pull-keep-index/"`; `keep_ref(repo, saved)` runs `update-ref <prefix><UTC stamp YYYYmmddTHHMMSSZ>-<saved[:8]> <saved> ""` (the empty old value never overwrites an existing ref), exiting 1 naming the saved commit on failure before anything is set aside. `set_aside` calls it between `stash create` and `reset --hard` and returns `(saved, ref)`. `saved_text(saved, ref)` reads "The local changes are saved in <saved> (ref <ref>)"; `recovery_text(repo, saved, ref)` passes the ref to `--put-back`. `drop_ref(repo, saved, ref)` runs `update-ref -d <ref> <saved>` after a successful put-back, then prints one stderr line "older saved changes kept under: <refs>" listing the other refs under the prefix (`for-each-ref --format=%(refname) refs/pull-keep-index/`), never deleting them. `--put-back <arg>` resolves its argument once, before any other step: `saved = rev-parse --verify -q <arg>^{commit}` (exit 1 as today when `<saved>^2` does not resolve); the ref is (1) `arg` itself when it starts with `REF_PREFIX`, else (2) the first ref by name from `for-each-ref --points-at <saved> --format=%(refname) refs/pull-keep-index/`, else (3) a new ref from `keep_ref(repo, saved)`. That choice comes before the clean-tree check and the apply, so a failed put-back always leaves a named ref. `stash apply`, `BUILT_PAGE_STASH`, every message and `drop_ref` use the resolved hash and that ref; a successful put-back drops the ref the same way a run drops its own. Docstring covers `--help`, the ref, its deletion rule and the older-refs line.

#### 2. Tests

**File**: `tests/scripts/test_pull_keep_index.py`
**Changes**: `--help` prints the usage, exit 0; a failed put-back leaves a ref under the prefix pointing at the saved commit and stderr names it (real fixture, no mock: a `reference-transaction` hook that, on `committed` for `refs/heads/`, recreates the set-aside file with other content; the hook fires on `set_aside`'s `reset --hard`, so the pull itself refuses on the unstaged file and the `stash apply --index` then stops with "would be overwritten". The test asserts only the failed put-back, the ref and the stderr naming it, never that the pull worked or that HEAD moved; the same shape as Phase 5's hook tests, and the mock at test line 804 is not the base); a clean run leaves no ref; `--put-back refs/pull-keep-index/<x>` succeeds and deletes that ref, and the driver's `BUILT_PAGE_STASH` holds the 40-character hash, not the ref name (a variant of `test_the_re_apply_names_the_saved_commit_to_the_built_page_driver`); `--put-back <hash>`: a ref already at the hash is deleted on success; no ref → success leaves no ref; no ref and HEAD moved with a conflicting commit → the run fails and leaves a new ref at the hash, which stderr names. Existing `saved_text` assertions updated.

Change file: "pull_keep_index keeps a named ref for the saved changes and prints --help".

### Success Criteria

A failed put-back never leaves the edits only in an unreferenced commit; `--help` prints usage.

#### Automated Verification

- [x] `python3 tests/parallel_tests.py test_pull_keep_index.py` (RED before: help and ref tests)
- [x] `bash tests/lint.sh claude/.claude/scripts/tools/pull_keep_index.py`

#### Manual Verification

- `python3 claude/.claude/scripts/tools/pull_keep_index.py --help` prints the docstring and exits 0.

## Phase 4: pull_keep_index built-page put-back through the merge driver

### Changes Required:

#### 1. Hand repair

**File**: `claude/.claude/scripts/tools/pull_keep_index.py`
**Changes**: `put_back_by_hand(repo, saved, ref, pages)` replaces `put_back_without_index`: (1) `git diff --binary saved^1 saved^2` with each page excluded through `:(exclude,literal)<page>` (a page name such as `p[1]` is a literal, never a glob; test line 217 covers the lookalike `p1`); when the diff output is empty the apply is skipped (git 2.34 has no `--allow-empty`, and `git apply` exits 128 on empty input), else `git apply --index --3way`; on failure `exit_rolled_back(repo, saved, ref, "staged", pages)`; (2) `tree = git write-tree`; (3) `git diff --binary saved^2 saved` minus pages (the same literal excludes), skipped the same way when empty, else `git apply --3way`; on failure `exit_rolled_back(repo, saved, ref, "unstaged", pages)`; (4) `git read-tree <tree>`; (5) per page write `saved^1:page`, `HEAD:page`, `saved:page` to temp files (a missing blob → empty file), read `git config --get merge.built-page.driver`, substitute `%O %A %B %P` with `shlex.quote`d paths, run through `sh -c` with cwd `git rev-parse --show-toplevel` and `BUILT_PAGE_STASH=<saved>`; non-zero → exit 1 "the built-page driver could not rebuild <page>: <stderr>" plus the add command and the ref; success → copy `%A` over the page; (6) `git add` with `page_stage_arguments(pages)`; a non-zero exit keeps today's stop (pull_keep_index.py:293-300): exit 1 "could not stage the rebuilt pages: <stderr>. To stage them, run: <add command>" plus `saved_text` and the ref. `exit_rolled_back` reads the conflicted files (`listed_paths --diff-filter=U`) first, showing git's stderr when there are none; runs `git reset --hard --quiet` (the saved commit is under the ref; untracked files are not touched); exits 1 with "pull_keep_index: the pull worked, but the <staged|unstaged> local changes conflict with it in <files> and were not put back. The tree is at the pulled HEAD with no local changes; the rebuilt pages <pages> were not made. <saved_text>. To put them back with the conflicts marked, run: `BUILT_PAGE_STASH=<saved> git -C <repo> stash apply <saved>`, fix the markers, then stage what was staged and `git add` the pages." It never says that a file is back. `put_back` routes here after a failed `stash apply --index` with no U entries when `staged_clash_paths` holds a built page and the driver is configured; otherwise `exit_unapplied`. `--put-back` uses the same `put_back`. Delete `put_back_without_index`; `staged_tree` and `restore_the_split` stay for `exit_unapplied`. Docstring rewritten for the six steps and the rolled-back stop.

#### 2. Tests

**File**: `tests/scripts/test_pull_keep_index.py`
**Changes**: incident shape (origin changes page `docs/p.md` and file `a`; local staged edits to `p.md`, `a` on other lines, `b`; unstaged edit to `c`; stub driver writes `rebuilt\n` to `%A`) → exit 0, `p.md == "rebuilt\n"` and staged, `a` and `b` staged with both sides, `c` unstaged, no ref left; the same through `--put-back <ref>` on the clean tree; a driver exiting 1 → exit 1 naming the page, the add command and the ref. Step 1 conflict, one test, the rewrite of line 159 (its fixture: `k` staged on the line origin changed, plus the page clash) → exit 1, stderr names `k`, "were not put back" and the ref; `git status --porcelain --untracked-files=no` is empty; the ref resolves to the saved commit. Step 3 conflict, one test, the rewrite of line 179 (its fixture: an unstaged conflict on `g`, plus the page clash) → the same assertions with "unstaged" in the message and `g` named (status empty after the rollback, not `UU g`). Empty-diff cases: only the page staged and nothing unstaged → exit 0, page rebuilt, no conflict message (steps 1 and 3 skipped). Other existing tests that the new route changes: line 199 (driver exits 1) now asserts exit 1 naming the page with `f` at HEAD and no `UU` entry (step 5 fails after `read-tree`); line 770 (a failed `git add` of the rebuilt pages, calling `put_back_without_index` at 795) moves to `put_back_by_hand` and keeps its assertions on "could not stage the rebuilt pages", the add command and the saved commit, plus the ref; line 803 (816 mocks `stash apply`, which the new path never runs) is deleted. Every other built-page test keeps its behaviour; only message assertions change.

#### 3. Real-driver run (D10 evidence)

**Agent-run**, once, before Phase 11. Paste every command and its result in the hand-back. `S` is the scratchpad and `B=python3 ~/agent-evals/bin/build_changes.py`.

1. `git clone --bare --no-local /home/brandon/dotfiles-herdr-tools-nov22 S/driver-origin.git`, then clone it to `S/driver-a` and `S/driver-b`. In each clone run `python3 ~/agent-evals/bin/install_merge_driver.py <clone>` (the command `.gitattributes` names) and check that `git -C <clone> config --get merge.built-page.driver` prints the driver.
2. In `driver-b`: `$B new "driver probe b" --by claude-code/<model id> --root S/driver-b/docs/changes`; fill the note it prints (kind, description, evidence, `## Change` section), copying the frontmatter shape of the newest note in `docs/changes/notes/`; `$B --check --root S/driver-b/docs/changes` until it passes, then `$B --root S/driver-b/docs/changes`; assert `git -C S/driver-b diff --quiet -- docs/changes/changelog.md` exits 1 (the page changed); append one comment line to the end of `install/stow`; commit everything and push.
3. In `driver-a`: the same with "driver probe a" (filled note, check, build), asserting `changelog.md` changed the same way; insert one comment line after line 1 of `install/stow`; stage the note, the rebuilt pages and `install/stow`; make one unstaged edit to `README.md`.
4. `python3 /home/brandon/dotfiles-herdr-tools-nov22/claude/.claude/scripts/tools/pull_keep_index.py S/driver-a`.

Pass when all hold: exit 0; `git -C S/driver-a diff --cached --name-only` lists the note, every page that changed and `install/stow`; `README.md` is listed only by `git diff --name-only`; `grep -F "driver probe a" docs/changes/changelog.md` and `grep -F "driver probe b" docs/changes/changelog.md` both match in `driver-a` (the page was rebuilt from both notes, not taken from one side); `$B --check --root S/driver-a/docs/changes` passes; no `refs/pull-keep-index/*` is left. Delete the clones afterwards. A failure is a failing criterion.

Change file: "pull_keep_index puts staged files back and rebuilds clashing built pages through the merge driver". Its text never writes the removed function's name: the built pages render each note's description, and Phase 11 bans that name in `docs/changes/*.md`.

### Success Criteria

The incident state ends with every local change back, staged files staged, pages rebuilt, in the run and through `--put-back`.

#### Automated Verification

- [x] `python3 tests/parallel_tests.py test_pull_keep_index.py` (RED before: incident-shape tests exit 1)
- [x] `bash tests/lint.sh claude/.claude/scripts/tools/pull_keep_index.py`
- [x] **Agent-run**: the real-driver run in step 3, output pasted in the hand-back

#### Manual Verification

N/A (the Agent-run step above is the driveable scenario).

## Phase 5: pull_keep_index in a shared checkout

### Changes Required:

#### 1. Shared route and lock

**File**: `claude/.claude/scripts/tools/pull_keep_index.py`
**Changes**: import `session_registry` and `file_lock`.

Lock: after `--help`, read `PULL_KEEP_INDEX_LOCK_SECONDS` once (default 300); a value that is not a positive integer exits 1 naming the variable. `main` resolves `repo` for both forms; the lock file is `<rev-parse --path-format=absolute --git-common-dir>/pull-keep-index.lock` (a failure there exits 1, "not a git repository"). The whole dispatch, `--put-back` and the pull alike, runs inside `with file_lock.hold_exclusive(lock, seconds)`; `LockTimeoutError` exits 1: "pull_keep_index: another run holds <lock>; nothing pulled or set aside".

Shared route, after `target` is known and before `set_aside`: `dirty = listed_paths(repo, "HEAD")` (tracked changes, staged or not); `other = session_registry.other_live_session_in(repo, os.environ.get("CLAUDE_CODE_SESSION_ID"))`. With both set, `shared_pull(repo, target, other, dirty)` runs and returns without reaching `set_aside`: (1) fetch: `remote, ref` = `target[0], f"refs/heads/{target[1]}"` when `target` is set, else from `configured_remote` and `branch_merge_ref` for the current branch (no branch → exit 1 "detached HEAD in a shared checkout"); `<branch>` in the fetch ref is the last path component of `ref`, the merge ref's branch, not the local name; when `git check-ref-format refs/pull-keep-index-fetch/<remote>/<branch>` fails (a remote of `.` or a URL) exit 1 "pull_keep_index: remote <remote> cannot name a fetch ref; nothing pulled or set aside"; `git fetch --quiet <remote> +<ref>:refs/pull-keep-index-fetch/<remote>/<branch>` (a failure exits 1 with git's error); `incoming = rev-parse --verify refs/pull-keep-index-fetch/<remote>/<branch>^{commit}`, then `update-ref -d` that ref (a named ref, not `FETCH_HEAD`, which another session's plain `git fetch` can rewrite between the two steps; the prefix differs from `refs/pull-keep-index/` so `for-each-ref` over the saved refs never lists it); this never reads `@{u}`, so it also covers `pull_target` returning `[]`. (2) Already held: `merge-base --is-ancestor incoming HEAD` passes → print "<branch> already holds <short incoming>; nothing pulled", run `set_upstream(repo, *target)` when `target` is set, return. (3) Diverged: `merge-base --is-ancestor HEAD incoming` fails → exit 1 "pull_keep_index: <holder_label(other)> also works in <repo> and the branch has local commits; nothing pulled or set aside. Dirty files: <dirty>. Commit them, or wait for that session to finish, then rerun." (4) Overlap: `overlap = sorted(set(listed_paths(repo, "HEAD", incoming)) & set(dirty))` non-empty → exit 1 "pull_keep_index: <holder> also works in <repo>; the pull would overwrite: <overlap>. Nothing was set aside. Commit those files, or wait for that session to finish, then rerun." (5) Merge: `git merge --ff-only --quiet <incoming>`; a failure exits 1 with git's stderr verbatim and "Nothing was set aside" (git's text is never parsed); on success run `set_upstream(repo, *target)` when `target` is set, return. A shared, clean tree and a solo run keep today's path. Docstring: one paragraph on the shared route and the lock variable.

#### 2. Tests

**File**: `tests/scripts/test_pull_keep_index.py`
**Changes**: `setUp` sets `CLAUDE_CONFIG_DIR` to a temp folder with `sessions/` and `CLAUDE_CODE_SESSION_ID=self-id` so existing tests stay solo. Helper `register_other(cwd)` writes a row whose `pid` is a live `sleep 600` child (killed in cleanup) and `sessionId` `other`. Keep-in-tree test: other session registered, the tracked file `bin/x` has the unstaged line `local-edit`, origin advanced on a different file; a `reference-transaction` hook acts only when `$1 = committed` and stdin names `refs/heads/`, then logs `kept=1` when `grep -q local-edit bin/x` matches (else `kept=0`) and appends `writer` to `bin/x` → exit 0, the log has at least one line and every line is `kept=1`, `bin/x` holds both `local-edit` and `writer`, no ref made, HEAD equals origin's tip. Overlapping dirty file → exit 1 naming the file and "Nothing was set aside", HEAD and file unchanged. Diverged + dirty + shared → exit 1 naming the dirty files, HEAD and file unchanged. No `CLAUDE_CODE_SESSION_ID` with a row for the caller's own cwd → the shared route. A targeted first pull on the shared route (no upstream set, origin has the branch) → `branch.<b>.remote` and `branch.<b>.merge` are set afterwards. A single-branch clone where `@{u}` does not resolve but the remote has the ref takes the shared route and fast-forwards. Solo route with the hook recreating the set-aside file → put-back fails "would be overwritten" and the printed ref exists. Lock (AC28): a Python child holds `<common dir>/pull-keep-index.lock` through `lib/file_lock.hold_exclusive`, prints `held` and sleeps until killed; the test waits for `held`; a run with `PULL_KEEP_INDEX_LOCK_SECONDS=1` exits 1 naming the lock with the tree untouched; `--put-back` under the same holder exits 1 the same way; `PULL_KEEP_INDEX_LOCK_SECONDS=x` exits 1 naming the variable.

Change file: "pull_keep_index never sets another session's edits aside in a shared checkout".

### Success Criteria

With a second live session in the repo, its files stay in the tree for the whole pull or the run refuses naming them and the way out; a mid-pull writer is pinned by a test.

#### Automated Verification

- [x] `python3 tests/parallel_tests.py test_pull_keep_index.py` (RED before: the keep-in-tree hook logs `kept=0`, because the edit was set aside while the rebase moved the branch)
- [x] `bash tests/lint.sh claude/.claude/scripts/tools/pull_keep_index.py`

#### Manual Verification

- **Agent-run**: in a `!` line, `echo "${CLAUDE_CODE_SESSION_ID:-unset}"`; if unset, report to the orchestrating session before merge, because every dirty push line on a diverged branch would then refuse.

## Phase 6: herdr-phase-change resolves a session name or a worktree path

### Changes Required:

#### 1. Resolver

**File**: `claude/.claude/scripts/tools/session_pane.py`
**Changes**: `resolve ARG` → `{"pane_id": "...", "via": "path"|"session"|"as-given"}`: (1) `ARG` an existing directory → claude agents (`agent == "claude"`) whose realpath cwd is inside it (`os.path.commonpath`); one → its pane; none → exit 1; several → exit 1 listing `pane_id cwd` lines; (2) `session_registry.row_for_name(ARG)` → its `sessionId` → the agent whose `agent_session.value` matches; none → exit 1 `session ARG has no herdr pane`; (3) else `as-given`. One `herdr-api agent list` call; failure exits 2 naming the call.

#### 2. Caller

**File**: `scripts/.local/bin/herdr-phase-change`
**Changes**: after argument parsing: `resolved=$(python3 "$session_pane" resolve "$target") || exit 1`, then `target=$(jq -r .pane_id <<<"$resolved")`; `session_pane` is defined in Phase 1 §4; resolver stderr passes through. Usage: the target may be a ListAgents name, a worktree path, a pane id or a herdr agent name; an existing directory wins over a same-named session.

#### 3. Tests

**Files**: `tests/scripts/test_session_pane.py`, `tests/scripts/test_herdr_phase_change.py`
**Changes**: `session_pane`: name → pane; path → pane; two agents in one path → exit 1 listing both; unknown → `as-given`; name with no pane → exit 1. `herdr-phase-change`: `STUB_HERDR_API` gains `agent list` printing two agents, each with `agent: "claude"`, one with cwd `$STATE_DIR/wt` and `agent_session.value` `s1`; `setUp` registers a row `name=lane-x, sessionId=s1` whose `pid` is a live `sleep 600` child killed in cleanup (`live_session_rows` drops dead pids, session_registry.py:48-50); `STUB_HERDR_API`'s `agent get` branch also appends `$3` to `$state/get-targets`; `herdr-phase-change lane-x "/code p"` and `herdr-phase-change $STATE_DIR/wt "/code p"` each leave the stub pane id as every line of `get-targets` and call `agent prompt` with it.

Change file: "herdr-phase-change takes a ListAgents session name or a worktree path".

### Success Criteria

A ListAgents name and a worktree path both reach the right pane without a herdr agent list dump.

#### Automated Verification

- [x] `python3 tests/parallel_tests.py test_herdr_phase_change.py` (RED before: `agent get lane-x` not found)
- [x] `python3 tests/parallel_tests.py test_session_pane.py`
- [x] `bash tests/lint.sh claude/.claude/scripts/tools/session_pane.py`

#### Manual Verification

- **Agent-run**: `python3 /home/brandon/dotfiles-herdr-tools-nov22/claude/.claude/scripts/tools/session_pane.py resolve <a live lane's ListAgents name>` (the worktree copy by path; `~/.claude/scripts` links to the master checkout, which has no such file) prints its pane id with `"via": "session"`.

## Phase 7: herdr-phase-change names the report-to session

### Changes Required:

#### 1. Marker

**File**: `scripts/.local/bin/herdr-phase-change`
**Changes**: before the status check:

```
sender_json=$(python3 "$session_pane" sender 2>/dev/null) || true
sender=$(jq -r '.name // empty' <<<"$sender_json" 2>/dev/null) || sender=""
reason=$(jq -r '.reason // empty' <<<"$sender_json" 2>/dev/null) || reason=""
[ -n "$sender" ] || { echo "herdr-phase-change: cannot name the sending session (${reason:-session_pane.py printed no JSON}), so the report-to line cannot be added; sent nothing" >&2; exit 1; }
```

Then (P2.5) `prompt="$prompt [report to session $sender]"` for slash and plain prompts alike, after the plain-prompt pane prefix. Header describes the marker.

#### 2. Tests

**File**: `tests/scripts/test_herdr_phase_change.py`
**Changes**: `setUp` sets `CLAUDE_CODE_SESSION_ID=orch` and registers `name=orchestrator-a` with a live `pid` (the Phase 6 `sleep 600` child); `/code docs/plans/x/plan.md` → last recorded prompt `/code docs/plans/x/plan.md [report to session orchestrator-a]`; no resolvable sender: a stub `session_pane.py` (through `HERDR_SESSION_PANE`; a Python file written with `write_text`, not `write_stub`, since the script runs it through `python3`) that branches on `sys.argv[1]`, answering `resolve` with `{"pane_id": "<arg>", "via": "as-given"}` exit 0 (the Phase 6 resolve step runs first) and `sender` with `{"name": null, "reason": "no session"}` exit 1 → exit 1, stderr shows `(no session)` and zero prompts recorded; existing sent-prompt assertions carry the suffix.

Change file: "herdr-phase-change names the report-to session in the prompt it sends".

### Success Criteria

A cleared worker's first prompt names the session it reports to; the test fails before the change.

#### Automated Verification

- [x] `python3 tests/parallel_tests.py test_herdr_phase_change.py` (RED before: no marker)

#### Manual Verification

- **Agent-run**: in one Bash call, the Phase 1 `export` of `HERDR_LANES_CLI` and `HERDR_SESSION_PANE`, then `/home/brandon/dotfiles-herdr-tools-nov22/scripts/.local/bin/herdr-phase-change <the Phase 1 probe lane's name> "/orient"` (the worktree copy by path; the stowed `herdr-phase-change` is master's), then `python3 "$HERDR_LANES_CLI" get <name>`; the probe pane shows the prompt ending in `[report to session <this session's name>]`, and the `get` output shows that text as `brief`. If the run treats the marker as a run note, report it to the orchestrating session.

## Phase 8: herdr-dev resume mode and herdr-lane-resume

### Changes Required:

#### 1. Resume mode

**File**: `scripts/.local/bin/herdr-dev`
**Changes**: a leading `--resume` sets `resume=1` and shifts; with it `claude_cmd="claude --resume $claude_session --name $fork_name"` (no `--fork-session`), same temp-file prompt path. Header documents it.

#### 2. Lane resume and close

**File**: `scripts/.local/bin/herdr-lane-resume` (new; bash, `set -euo pipefail`, PATH export, `usage()` from the header)
**Changes**: `<name>`: (1) `python3 "$lanes_cli" get "$name"`; null → exit 1 listing names from `list`; (2) worktree folder missing → exit 1 "worktree gone; run herdr-lane-resume --close <name>"; (3) empty `session_id` → exit 1 "the fork never reported a session id; open the worktree and run claude there"; (4) a herdr agent with cwd inside the worktree → exit 1 "lane is live in pane <id>"; (5) a workspace whose `worktree.checkout_path` is the worktree → exit 1 "workspace <id> is already open on it; close it, then rerun"; (6) under herdr `herdr worktree open --cwd <main> --path <wt> --label <name> --focus`; under tuios `herdr-api workspace create --cwd <wt> --label <name> --focus` then `workspace focus`; (7) `ws` from `.result.workspace.workspace_id`; `herdr-dev --resume <wt> <ws> <session> <brief>`; exit 0. Setup: `bin_dir` as in herdr-worktree (herdr-dev and herdr-worktree-prune run from `$bin_dir`); `lanes_cli` defined as herdr-worktree does; `-h` prints usage.

`--close <name>`, in this order; steps 1 and 2 leave everything as it was when they stop: (1) `entry=$(python3 "$lanes_cli" get "$name")`; null → exit 1 listing the names from `list`; `wt` is the entry's `worktree`, through realpath when the folder exists. (2) Working agent: `herdr-api agent list` (a failure exits 1 naming the call: fail-closed, nothing changed); any `agent == "claude"` entry whose realpath cwd is inside `wt` with `agent_status == "working"` → exit 1 "lane <name> has a working agent in pane <id>; wait for it to finish, then rerun". (3) Close the workspace: `herdr-api workspace list`, each workspace whose realpath `worktree.checkout_path` equals `wt`; under tuios, where workspaces carry no `worktree`, match `label == name` instead (the coder checks the shim's list shape first and uses `checkout_path` when the shim has it); close each with `herdr workspace close <id>`, under tuios `herdr-api workspace close <id>`; a failed close → exit 1 naming the workspace, entry kept, nothing pruned; after a close, poll `herdr-api agent list` every 0.5 s for up to 10 s until no agent's cwd is inside `wt`; on timeout warn "an agent still runs in <wt>; the prune will keep it" and go on. (4) `python3 "$lanes_cli" remove "$name"`; when the worktree folder is already gone, say so and still remove the entry (P2.6). (5) When `main_checkout` exists, `(cd "$main_checkout" && "$bin_dir/herdr-worktree-prune" --apply)`, exiting with its code, output passed through; otherwise say the main checkout is gone and exit 0.

#### 3. Tests

**Files**: `tests/scripts/test_herdr_dev.py` (new), `tests/scripts/test_herdr_lane_resume.py` (new)
**Changes**: `herdr-dev`: stub `herdr-api` answering `workspace get`, `pane list`, `pane split`, `pane wait-output` with shaped JSON, and `{}` with exit 0 to every other verb (`pane current` 51, `pane resize` 100 and 136, `tab create` 140, `tab focus` 145 and 165, `pane focus` 166, `tab rename`, `pane rename`, `pane send-keys` and the console-tab calls at 108-109, 131, 61, 68, 141-144: the script runs under `set -e`), and recording `pane send-text`; `--resume` types `claude --resume s1 --name <basename>` without `--fork-session`; positional fork mode still types `--fork-session`. `herdr-lane-resume`: stubs copied beside a copy of the script so `$bin_dir` finds them: `herdr` (records argv), `herdr-api` (`agent list` and `workspace list` read state files; `workspace close` records argv and empties the agent list), `herdr-dev` (records argv), `herdr-worktree-prune` (records cwd and argv, exit 0); real `lanes.py` under a temp `XDG_STATE_HOME`; resume after the file exists → `herdr worktree open --cwd M --path W --label N --focus` and `herdr-dev --resume W <ws> s1 <brief>`; each resume exit-1 case. `--close`: an idle agent in W and workspace `wX` with checkout path W → in order `herdr workspace close wX`, the entry gone from `lanes.py list`, the prune run with `--apply` in M; a `working` agent in W → exit 1, no close recorded, entry still listed, no prune; the close stub exits 1 → exit 1, entry still listed, no prune; `TUIOS_SOCKET` set → `herdr-api workspace close wX` recorded; the agent never leaves (the close stub keeps the list) → a warning, then the entry is removed and the prune runs; no entry → exit 1; the worktree gone → entry removed and the prune runs.

Change file: "herdr-lane-resume reopens a dead lane from its lane file and closes finished ones".

### Success Criteria

A dead lane restarts in one command from its lane file; a closed lane leaves the lane list.

#### Automated Verification

- [x] `python3 tests/parallel_tests.py test_herdr_lane_resume.py` (RED before: script missing)
- [x] `python3 tests/parallel_tests.py test_herdr_dev.py` (RED before: `--resume` taken as the directory)

#### Manual Verification

- **Agent-run** on the Phase 1 probe lane, with the same two variables and worktree paths as Phase 1: (1) `herdr workspace close <its ws>`; (2) `/home/brandon/dotfiles-herdr-tools-nov22/scripts/.local/bin/herdr-lane-resume <name>`: the workspace reopens and the claude pane runs `claude --resume <session_id> --name <name>` with no `--fork-session` and the brief; (3) leave the lane open: Phase 10's check runs `--close` on it against the real prune and deletes the scratch clone.

## Phase 9: lane-status

### Changes Required:

#### 1. Status tool

**Files**: `claude/.claude/scripts/tools/lane_status.py` (new), `scripts/.local/bin/lane-status` (new: `exec python3 "$HOME/.claude/scripts/tools/lane_status.py" "$@"`)
**Changes**: memory from `/proc/meminfo` `MemAvailable` on Linux, `vm_stat` free+inactive+speculative pages × `sysctl -n hw.pagesize` on macOS, else a `memory: cannot read` line; `df -Pk` on the scratch root (`hook_input.claude_code_temp_root`) or its nearest existing parent; `du -sk` of the root, skipped when missing; lanes from `lane_entries.all_entries()` plus one `herdr-api agent list`, claude agents matched by realpath cwd inside the worktree. Lines: `<name>: no agent`, `<name>: <status>` for any status other than `working`, `<name>: worktree gone`, `memory: <N.N> GB available, under <T> GB`, `scratch: <N.N> GB free on <dir>, under <T> GB`, `scratch: <root> holds <N.N> GB, over <C> GB`. Env `LANE_STATUS_MIN_MEMORY_GB` (8), `LANE_STATUS_MIN_SCRATCH_GB` (1), `LANE_STATUS_SCRATCH_CAP_GB` (4). Exit 0 nothing printed, 1 something printed, 2 bad lane file or failed herdr-api/df/du.

#### 2. Tests

**File**: `tests/scripts/test_lane_status.py` (new)
**Changes**: PATH stubs for `herdr-api`, `df`, `du`; temp `XDG_STATE_HOME`; `CLAUDE_CODE_TMPDIR` at a temp folder; `LANE_STATUS_MIN_MEMORY_GB=0`. A closed lane (added, then removed) is absent; stub `df` reporting 100 KB free prints the scratch free line and exits 1; working agent and healthy stubs → no output, exit 0; idle agent → `<name>: idle`; no agent → `no agent`; `du` over the cap → the holds line; herdr-api failing → exit 2; threshold 100000 prints the memory line (Linux only).

Change file: "lane-status reports low memory, scratch space and open lanes that are not working".

### Success Criteria

One command a Monitor until-loop can call reports memory, scratch and every open lane not working, and says nothing for a closed lane.

#### Automated Verification

- [ ] `python3 tests/parallel_tests.py test_lane_status.py` (RED before: missing)
- [ ] `bash tests/lint.sh claude/.claude/scripts/tools/lane_status.py`

#### Manual Verification

- **Agent-run**: `python3 /home/brandon/dotfiles-herdr-tools-nov22/claude/.claude/scripts/tools/lane_status.py; echo $?` (the worktree copy by path; no stowed `lane-status` exists yet) lists the Phase 1 probe lane when its agent is not working, plus any other open lane not working, and exits 0 or 1. Human-only: the macOS `vm_stat` path is checked on a Mac before the item closes.

## Phase 10: prune keeps open lanes; `--close` runs it

### Changes Required:

#### 1. Lane keep

**File**: `scripts/.local/bin/herdr-worktree-prune`
**Changes**: `LANE_OPEN = "open lane"`; `World` gains `lane_worktrees: list[tuple[str, str]] | None`; `read_lanes()` runs `python3 <lanes cli> list`, where `<lanes cli>` is `os.environ.get("HERDR_LANES_CLI")` or `os.path.expanduser("~/.claude/scripts/tools/lanes.py")`, parses `lanes[].name/worktree`, returns `None` plus a reason in `notes` on any failure; called where `World(...)` is built (line 471) so `remove_one`'s re-check reads it again. `check_lane_open`: `None` → `Keep(CANNOT_CHECK, "the lane list could not be read: <reason>")`, with a comment naming the fail-closed choice; a tree equal to or inside an open lane's worktree → `Keep(LANE_OPEN, "lane <name> is open; herdr-lane-resume --close <name> closes it")`. Inserted in `CHECKS` after `check_default`. Docstring: one condition bullet, and `refs/pull-keep-index` in the never-touched list. If `wc -l` passes 999, stop and report to the orchestrating session before any split.

#### 2. Tests

**File**: `tests/scripts/test_herdr_worktree_prune.py`
**Changes**: both `setUp` methods (lines 263 and 1162) set `XDG_STATE_HOME` to an empty temp folder and `HERDR_LANES_CLI` to the tree's `lanes.py`. A merged, clean, agentless worktree with an open lane entry is kept with `open lane`; after `lanes.py remove` it is removed by `--apply`; `HERDR_LANES_CLI` at a missing file keeps every tree with `cannot check` and removes nothing.

Change file: "herdr-lane-resume --close runs the worktree prune, which keeps open lanes".

### Success Criteria

Closing a merged lane with `herdr-lane-resume --close` closes its workspace, then removes its worktree, with no new hook process; an open lane's worktree is never removed. After one `--close`, no worktree remains whose lane is closed, merged and clean; current, locked, stashed, held and squash-merged trees stay.

#### Automated Verification

- [ ] `python3 tests/parallel_tests.py test_herdr_worktree_prune.py` (RED before: the open-lane tree is removed)
- [ ] `awk 'END { exit NR >= 1000 }' scripts/.local/bin/herdr-worktree-prune`
- [ ] `ruff check --no-cache scripts/.local/bin/herdr-worktree-prune`

#### Manual Verification

- **Agent-run**, on the Phase 1 probe lane (still open, in the scratch clone `S/clone`), with the Phase 1 `export` of `HERDR_LANES_CLI` and `HERDR_SESSION_PANE` repeated in each Bash call: (1) the probe brief is a no-op, so the branch has no commits of its own and a clean tree, and it already reads as merged; wait until `herdr-api agent get <name>` reports `agent_status` other than `working` (`--close` refuses a working agent); `cd S/clone && /home/brandon/dotfiles-herdr-tools-nov22/scripts/.local/bin/herdr-worktree-prune` (dry run, worktree copy by path) lists the probe worktree under `open lane`; `n=$(git -C S/clone worktree list | wc -l)`. (2) `/home/brandon/dotfiles-herdr-tools-nov22/scripts/.local/bin/herdr-lane-resume --close <name>`: the probe workspace closes, `python3 "$HERDR_LANES_CLI" list` no longer lists the lane, and `git -C S/clone worktree list | wc -l` prints `n - 1` (the real prune removed the merged, clean, agentless tree: AC9 and this phase's criterion). (3) Delete `S/clone`. The probe lane ends here.

## Phase 11: Close-out — change pages, propagation sweep, full suite

### Changes Required:

#### 1. Pages and sweep

**Files**: `docs/changes/` (the built pages), docstrings and headers of every script changed above
**Changes**: `free -g` (8 GB or more available) then `bash tests/run.sh`; `bash tests/lint.sh` on every changed `.py` and test file; `python3 ~/agent-evals/bin/build_changes.py --root /home/brandon/dotfiles-herdr-tools-nov22/docs/changes` rebuilds the pages; `rg -n --hidden "put_back_without_index" claude opencode scripts docs/changes/*.md` finds nothing (`--hidden` because rg skips `scripts/.local/bin` without it; `herdr-worktree-watch.log` and the `herdr-dev <worktree> <ws>` fallback steps are still live, so they are not banned; never search or edit `docs/plans/` or `docs/changes/notes/`). Lines for files this lane may not edit go to the orchestrating session in the hand-back, not into the files: repo `CLAUDE.md` `scripts` package line gains `herdr-lane-resume` and `lane-status`; `claude/.claude/orchestration.md` lines 35-36: close a merged lane with `herdr-lane-resume --close <name>`, and herdr-phase-change takes a ListAgents name and adds the report-to line itself. No agent or skill file changed, so there is no opencode port.

### Success Criteria

The whole suite and lint pass; the change pages are rebuilt; no stale reference to a removed name remains.

#### Automated Verification

- [ ] `bash tests/run.sh`
- [ ] `python3 ~/agent-evals/bin/build_changes.py --check --root /home/brandon/dotfiles-herdr-tools-nov22/docs/changes`
- [ ] `rg -n --hidden "put_back_without_index" claude opencode scripts docs/changes/*.md` (ban: no match)

#### Manual Verification

N/A (infra-only).

## Phase 12: Close pass

`/close-branch`: scripts first, then four report-only reviewers in parallel on the whole branch diff (correctness, structure, test intent, plan and acceptance-criteria reconciliation), one `coder` that fixes every finding and writes every owed test, then a report-only gate on the fix diff alone, then the recap sheet. Root-cause rule: a cast or default papering a fixable loose structure is a finding; fix the source.

### Success Criteria

Quality checks green; every reviewer finding fixed, shown wrong, or (an ask that changes a ticket AC) put to the orchestrating session; the fix-diff gate passed; every acceptance criterion mapped to a test or explicitly retired; concentration counts stated; recap and smoke-test checklist delivered; real diff size reported against the 1,900-line estimate.

#### Automated Verification

- [ ] `bash tests/run.sh`
- [ ] `git diff --name-only 8436be97..HEAD | grep -c '^tests/scripts/test_' | awk '$1 >= 13 {exit 0} {exit 1}'` (phases 0-10 name 13 test files, 6 edited and 7 new; every one is in the diff)
- [ ] `python3 ~/agent-evals/bin/build_changes.py --check --root /home/brandon/dotfiles-herdr-tools-nov22/docs/changes`

#### Manual Verification

- The recap names the branch, the final hash, the suite count, the Agent-run evidence from Phases 4, 5 and 10, and the CLAUDE.md and orchestration.md lines handed to the orchestrating session.
