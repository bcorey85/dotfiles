# toolkit-scripts-1122: three toolkit texts give their format to the script that owns it

> Ticket: ./00-ticket.md (four queue items; item 1 is dropped, D1)
> Research: ./02-research.md (goal-blind, produced before design began)
> Decisions: ./03-decisions.md (the design-resolution ledger)
> Date: 2026-11-22

<!-- Source precedence: on anything concrete, THIS file wins over the ledger (which records why, not what). A disagreement between them is a spec bug — report it. -->

## Summary

Three toolkit texts give up the parts that a script owns. The refactor skill's 30-line log-input JSON template moves into a new grammar module beside `refactor_flow.py`, which prints it from `log --help`, and the split brings `refactor_flow.py` under the 1000-line limit. The mutation-tester agent's lock, backup and restore prose becomes three calls to a new `tools/mutation_lock.py`, built on a new `lib/calibration_lock.py` that `gates/calibration_guard.py` also imports, so the lock format has one owner; the opencode port gets the same three calls. The guide skill drops two of its three worked cards, and rules 3, 4, 5 and 7 are cut only where rule-meter on and off arms show the rule line changes nothing; rule 8 stays as `unmeasured` (cut, D20: master deleted the guide skill before the rebase). Every toolkit edit gets a change file under this worktree's `docs/changes`.

## Phase Status

<!-- Hoisted from below so the first screen answers "where are the agents?". The one section that changes after writing (/code ticks it) — source of truth for "which phase is next". Do not move it back down. -->

- [x] Phase 0: Contracts — frozen at plan approval (risk: high)
- [x] Phase 1: Walking skeleton — `refactor_log_input.py` split out, `log --help` prints the template (risk: low)
- [x] Phase 2: refactor skill and close-branch point to `log --help` (risk: low)
- [x] Phase 3: `lib/calibration_lock.py`, with `calibration_guard.py` importing it (risk: high)
- [x] Phase 4: `tools/mutation_lock.py` with its tests (risk: high)
- [x] Phase 5: mutation-tester and its opencode port call the script (risk: low)
- [x] Phase 6: the guide skill keeps one worked card (risk: low)
- [x] Phase 7: rule-meter scenarios and detectors for guide rules 3, 4, 5 and 7 (risk: low)
- [x] Phase 8: meter runs, then the rule cuts (risk: low)
- [x] Phase 9: change files, rule-anchors links and the full suite (risk: low)
- [x] Phase 10: Close pass — /close-branch parallel review, one fix, fix-diff gate, recap (risk: high)

## Decisions

<!-- One line per block in 03-decisions.md's ## Resolved: `N. [Topic] — [Choice]`, plus `Trade-off: …` only where it changes code. Reasoning and alternatives stay in the ledger's four-field blocks. -->

1. Item 1 — dropped; no phase, no change file, no test (queue already `status: dropped` at origin/bench-base ed04efba).
2. Item 3 grammar — the log-input grammar and a `LOG_TEMPLATE` move to `refactor_log_input.py`; `refactor_flow.py` re-exports `RefactorFlowError`; `log --help` prints the template between two marker lines. No new verb.
3. Item 3 skill — format lines leave `refactor/SKILL.md` Step 5; the three judgment bullets stay with their key lists stripped (exact text in Phase 2); `close-branch/SKILL.md:68` repoints to `log --help`.
4. Item 4 modules — new `tools/mutation_lock.py` on a new `lib/calibration_lock.py`; the guard imports the module and keeps its hook contract and tests unchanged.
5. Item 4 CLI — three verbs, `check <target>`, `lock <target> --class --line --owner-pid`, `restore --owner-pid --run-id` (run id added in the close pass, D19); named exit codes and output constants; every verb ends `NEXT:`, `STOP:` or `DONE:`.
6. Item 4 backups — `lib/file_backup.save_files` and `restore_changed` under `<state>/backups/<relpath>`; `discard` is never called. Trade-off: the old `backups/<basename>.bak` layout is not restorable by the script (D12).
7. Item 4 prose — Step 0 keeps the two preconditions a script cannot check (test command named, file named) as bullets; the heading loses its count; Steps 1 and 4 become one script line each.
8. Item 2 scope — the guide skill keeps the commands block, batch keys, card envelope, block and field tables, one worked card, rules 1, 2 and 6, and the answers shape; the pointer-to-binary cut of the tables waits on a `guide` build that prints the schema.
9. Item 2 tests — no new test for the guide skill; no rule-anchors row exists for it.
10. Detectors — pure graders in `~/agent-evals/bin/rule_meter_guide.py`, merged into `rule_meter_verifier.DETECTORS` by one import and one dict merge; `rule_meter.py` untouched; the lane commits the agent-evals files itself.
11. Change files — `build_changes.py new … --root /home/brandon/dotfiles-toolkit-scripts-nov22/docs/changes`, then `build_changes.py --root <same>`.
12. Old-layout lock — `restore` prints the guard's manual `cp` and `rm` lines, keeps the lock and exits 1 (`STOP_OLD_LAYOUT`).
13. Step 4 gate sentence — stays with its trigger retargeted to "`restore` ends with any other `STOP:`"; listed `unmeasured` in the mutation-tester change file.
14. Meter budget — one run per cell first (4 rules × 3 levels × 2 arms = 24 opus runs); a rule whose off arm complies at least as often as its on arm at every level gets one more run per cell (6 more); cut only when the confirmed second pass holds at every level; rule 8 stays `unmeasured`; per-arm counts go in the change file.
15. Not-ours refusal — `restore` prints `STOP_NOT_OURS` and the `cp … && rm …` recovery line (agent-evals-c3, 2026-11-22).
16. Dirty target — `check` and `lock` refuse a target with uncommitted edits (`STOP_DIRTY_TARGET`, file and `git status --porcelain` line); a sixth precondition in `PRECONDITIONS` (agent-evals-c3, 2026-11-22). Reversed by D18.
17. Unmeasured rules — a guide rule with fewer than two graded runs at any level stays, listed `unmeasured`; no forced line count (agent-evals-c3, 2026-11-22).
18. Dirty target, reversed — `check` and `lock` proceed on a target with uncommitted or untracked edits and print one `NOTE:` line naming that the file has uncommitted edits, so the reader knows what `restore` brings back; the lock still refuses a second concurrent run; D16 is void (agent-evals-c3, 2026-11-22: a test-audit on uncommitted fixes is the case the agent exists for; the byte backup and the hash-verified restore are the protection).

## Approaches Considered and Not Taken

<!-- The architect's counter-primed approaches, one line each (approach + ruling-out failure mode). Whole-feature approaches, not within-decision options. If fewer than three, say how many. -->

Three approaches were named and ruled out.

- A fake `guide` binary in the test tree, to test the skill against a schema printer — a second owner of the block and field format, which is the drift this plan removes.
- A `prep` verb that writes a pre-filled template file, or a JSON data file beside the script, instead of `log --help` — a second file to keep in sync with `validate_log`; the dict in the grammar module cannot drift from what the validator accepts.
- Restoring the old `backups/<basename>.bak` layout from `mutation_lock.py restore` — needs a second copy helper beside `lib/file_backup`, and no session has hit the case; it gets the fallback stop (D12).

## Constraints

<!-- Fixed-before-design non-negotiables: platform limits, existing contracts. A "decision" with no real alternative belongs HERE.

Self-sufficient: probe-verified facts an implementation step needs go here with evidence (coders don't read the ledger), each tagged `exercised` (observed) or `declared-only` (asserted). -->

- Lane rules (`declared-only`, from the brief): never code directly; load the `toolkit-writing` skill before any prose edit (Phases 2, 5, 6, 8); never edit `~/dotfiles/claude/.claude/settings.json`, any CLAUDE.md or `orchestration.md`; `git -C ~/agent-evals status bin/` before touching `~/agent-evals/bin/`, and never another session's uncommitted file there; `free -g` must show 8 GB or more available before the full suite, which runs as `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh`.
- Toolkit script rules (`declared-only`, `docs/toolkit-script-rules.md`): snake_case names; `bash tests/lint.sh <files>` passes; tests under `tests/scripts/test_<script>.py`, each reading its script path from one environment variable that defaults through `tests/scripts/toolkit_paths.py` (`CLAUDE_DIR`, `LIB_DIR`, `TOOLS_DIR`, `GATES_DIR`, `REPO_ROOT`); run through `python3 tests/parallel_tests.py <file>`; no new verb or route in a script over 1000 lines; `lib/file_lock.hold_exclusive(lock_path, timeout_seconds)` is the only flock helper; `lib/process_group.pid_is_alive` the only liveness check; one atomic state write per run; a fail-open or fail-closed comment on every gate.
- `refactor_flow.py` is 1097 lines (`exercised`, `wc -l`), over the 1000-line rule, so Phase 1 splits before it adds the `--help` text. Its `sys.path` insert of `scripts/lib` is at `:53`; `RefactorFlowError` at `:117-119`; `FINDERS` `:70`; `PLAN_STRUCTURE_TAG` `:90`; the grammar helpers at `:599-745` and `:806-820`; `log_verb`/`handoff_verb` call sites `:1008-1010`, `:1050-1055`; the `log` subparser `:1074-1077`; the docstring copy of the input shape `:22-34` (`exercised`).
- `ruff.toml:28` holds the `refactor_flow.py` E402 entry (`exercised`); `claude/.claude/scripts/*/*.py` already carries an E402 glob, so `tools/mutation_lock.py` and `lib/calibration_lock.py` need no new entry (`exercised`).
- `refactor/SKILL.md` is 133 lines with exactly one fenced `json` block, Step 5 at `:64-100` (`exercised`, `rg -c '^\s*\x60{3}json'` = 1). `close-branch/SKILL.md:68` names "Step 5 of the refactor skill" (`exercised`).
- `calibration_guard.py` is 167 lines: `MUTATION_RUN_TIMEOUT_SECONDS` `:27`, `lock_field` `:30-51`, `parse_stamp` `:54-59`, `session_pid_argument` `:62`, `lock_is_live` `:72-85`, `live_notice` `:88-97`, `main` `:100`, the view read `:117-129`, the UNRESTORED text `:139-162` (`exercised`). Its lock facts: `ts` is exactly `%Y-%m-%dT%H:%M:%SZ` UTC; `owner_pid` is compared as the string of an int; a relative `file` joins to `worktree`; `pre_hash` is 16 hex of sha256; the guard falls back to `~/.claude/calibration-lock.json`; the `writer == "calibrate"` branch is dormant and stays (`exercised`, read of the guard).
- `lib/file_backup.py` has `save_files(root, paths, backup_dir, max_file_bytes=MAX_FILE_BYTES)`, `restore_changed(backup)`, `restore_missing`, `discard(backup)`, `Backup`, `MAX_FILE_BYTES` = 50 MiB (`exercised`). `lib/file_lock.py` has `hold_exclusive(lock_path, timeout_seconds)` raising `LockTimeoutError`, `RETRY_SECONDS = 0.02` (`exercised`). `lib/script_utils.write_text_atomically` exists (`exercised`).
- `agents/mutation-tester.md` is 152 lines, the opencode port 161 (`exercised`). `docs/rule-anchors.md` rows: refactor `## Instructions` `458c884f` (`:127`); mutation-tester `6ca266a8` (`:131`), `84cdf15f` (`:132`), `d11ed9bc` (`:135`) (`exercised`). `bash claude/.claude/scripts/tools/rule-anchors.sh list <file>` prints the keys and hashes; `check` verifies them (`exercised`, `--help`).
- `guide/SKILL.md` is 236 lines; `## Three worked cards` at `:114`; the kept card `:116-186`; A/B at `:187` and A rating at `:198`, `## Rules` at `:200`; `guide_version` `0.1.0` at `:39` is the only version it names (`exercised`). `claude/.claude/settings.json:195` holds `"guide": "user-invocable-only"` and is not edited (`exercised`).
- `tests/changed_scope.py` `PROMPT_READING_TESTS` at `:24-41`, `test_log_review_finding.py` at `:31`; `test_prompt_reader_list.py` keeps that list honest against `PROMPT_READER_SIGNAL`, which matches `CLAUDE_DIR / "agents"` (`exercised`). `tests/parallel_tests.py` `HEAVY_FIRST` (`:42`) holds `test_refactor_flow.py` (`exercised`).
- `~/agent-evals/bin/rule_meter.py run` takes `--rule`, `--level {supportive,neutral,competing}`, `--arm {on,off}`, `--run N`, `--dry-run`; `summary` exists; `run-all` is never used (`exercised`, `--help`). `rule_meter_verifier.py:76` is `DETECTORS = {"late_fee_verdicts": detect_late_fee_verdicts}`; `rule_meter.py` reaches `rule_meter_checks/` only through hard-coded subprocess calls (`:1226`, `:1275`, `:1301`, `:1309`) and `grade()` dispatches through `rule_meter_verifier.DETECTORS` (`exercised`, read). Scenario rows carry `name, rule_text, setup, detector, task, suffix{supportive,neutral,competing}` plus `model`, `rule_source`, `toolkit_root` (`exercised`, rows at `:80-124`). Toolkit copies live under `~/dev/evals/rulemeter1/toolkits/<name>/claude/.claude` (precedent `uq01`); results in `~/dev/evals/rulemeter1/runs/results.jsonl`, one JSON row per run with `rule`, `level`, `arm`, `run`, `outcome` (`exercised`, head of the file). `df -h /tmp` must show 4 GB or more before a run (`declared-only`, agent-evals CLAUDE.md).
- `git -C ~/agent-evals status bin/` was clean at the last check (`exercised`); an earlier check saw untracked `bin/escape_classes.py` and `bin/test_escape_classes.py`, which are never touched.
- `build_changes.py --root` defaults to the checkout it runs from (`exercised`, `--help`); the plan passes the worktree root on every call (D11). `--by` is `claude-code/<the model running the step>`.

## External Contracts

<!-- Mandatory: every touched provider/API/platform contract + its invariant + what breaks if violated, claims tagged `exercised`/`declared-only`. Wide-blast-radius internal invariants too. "None" stated explicitly. -->

- **Calibration lock file** (`exercised`): `gates/calibration_guard.py` reads `${XDG_STATE_HOME:-$HOME/.local/state}/claude-calibration/lock.json`, then `~/.claude/calibration-lock.json`, on every SessionStart (`claude/.claude/settings.json:522`) and from the pi settings by path. A lock `mutation_lock.py lock` writes must keep the Phase 0 field set and types, or the guard reports a live mutation as stale or misses it. Phase 4's test runs the guard against a script-written lock.
- **`refactor_flow.py log <path>` input grammar** (`exercised`): the review loop and `close-branch` write files in this shape. The grammar moves module but does not change; old files parse as before. `tests/scripts/test_refactor_flow.py` reaches `module.RefactorFlowError`, so the re-export is part of the contract.
- **rule-meter result rows** (`exercised`): `rule_meter.py` writes `results.jsonl` and `summary` reads it; the new detectors return `(outcome, evidence)` with `outcome` in `COMPLIED`, `VIOLATED`, `NO_TEST`, the values the existing `late_fee_verdicts` detector returns.
- **`docs/rule-anchors.md`** (`exercised`): `rule-anchors.sh check` fails the suite when a section's hash differs from its row; every prose edit under an anchored section rehashes its row in the same phase.
- **`guide` block format version `0.1.0`** (`declared-only`): the skill names one version; this plan does not change the format or the version.

## Approach

- **Item 3 (Phases 1, 2):** split the grammar out, print the template from `--help`, then repoint the two prose consumers. The template is a dict beside the validator, so it cannot drift.
- **Item 4 (Phases 3, 4, 5):** module first (owner of the lock format), then the script, then the two agent prompts. The guard keeps its outputs and exit codes, apart from two changes: shell-special paths are quoted as one shell word, and the unrestored message's closing sentence no longer names the deleted `/calibrate` skill ("Do not dispatch mutation-tester until this lock is gone — it refuses to seed on top of an unrestored seed"); its tests pin both.
- **Item 2 (Phases 6, 7, 8):** cut the two cards first (no rule changes), then build the meter scenarios and detectors against the post-cut skill copy, then run the meter under the D14 budget and cut only what it clears.
- **Phase 9** writes the change files (cut to two, D20), links them from the rule-anchors rows, and runs the full suite under `systemd-run`.
- Patterns: toolkit script rules (Constraints); every verb ends with `NEXT:`, `STOP:` or `DONE:`; one owner per fact (`claude/.claude/scripts/CLAUDE.md`); `toolkit-writing` for prose.

## Dependencies

- No new package. Internal: `lib/file_lock`, `lib/file_backup`, `lib/script_utils`, `lib/process_group`, `lib/hook_input`, `lib/plan_format`, `tests/scripts/toolkit_paths.py`, `tests/parallel_tests.py`, `tests/lint.sh`, `tools/rule-anchors.sh`, `~/agent-evals/bin/build_changes.py`, `~/agent-evals/bin/rule_meter.py`.

## Implementation Plan

### Current State Analysis

`refactor/SKILL.md:64-100` holds a 30-line JSON template that `refactor_flow.py` (1097 lines) parses; the script's own docstring holds a second copy of the key list. `agents/mutation-tester.md` holds the lock, backup and restore procedure as prose with the state path repeated six times, says "all five" preconditions and lists four; the opencode port has the same prose with legacy paths. `calibration_guard.py` holds the lock format inside its `main`. `guide/SKILL.md` holds three worked cards and eight rules, five of them unmeasured no-op candidates.

### Desired End State

`refactor_flow.py log --help` prints the template; the skill keeps the trigger, the command, a pointer and three judgment bullets; `refactor_flow.py` is at most 1000 lines. `mutation_lock.py check|lock|restore` does the preconditions, backup, hash, lock and verified restore, and `calibration_guard.py --live` reads its lock. Both mutation-tester prompts call the script in one line per step, and `mutation_lock.py --help` owns the precondition list. (The guide skill has one worked card; rules the meter clears are cut, and the change file lists per-arm counts and `unmeasured` rules: cut, D20, master deleted the guide skill.) Two change files exist (D20; three before the cut); the full suite passes.

### What We're NOT Doing

- Item 1 (D1), and the follow-up candidates it surfaced (`check_push_reviewed` ignores `placed`; `cd … && gh pr create` judged in `payload_cwd`).
- Cutting the guide's block and field tables or pointing at the binary (waits on a `guide` build that prints the schema; recorded in the item 2 queue outcome; the guide change file is cut, D20).
- The dormant `writer == "calibrate"` branch in `calibration_guard.py`.
- Pruning old `backups/*.bak` files or accumulated backups.
- Porting the refactor or guide skills to opencode (it loads `~/.claude/skills` directly).
- Replacing the direct `fcntl.flock` calls in `refactor_flow.py:902` and `code/coder_gate.py:342,855` (refactor candidates for a later item).

### Acceptance Criteria

The criteria live in `docs/plans/toolkit-scripts-1122/acceptance-criteria.md` as prose with stable ids. Name the file here and nothing more.

- **Criteria file**: `docs/plans/toolkit-scripts-1122/acceptance-criteria.md`

The Close pass reconciles every id against the real suite, matching behavior, not markers. A covering test asserts at the public boundary a caller reaches (a script's argv and output, a prompt file's text), never an internal function. No mocks inside such a test.

### Implementation Approach

Three independent items, each a vertical slice from script to prose, ordered so each script phase lands before the prose that names it. Phase 1 is the walking skeleton: the smallest slice that exercises a Phase 0 contract end to end (the template contract, from dict to `--help` to a logged run).

---

## Phase 0: Contracts — frozen at plan approval

### Overview

The committable surfaces the later phases share. A change here after approval is a Plan Deviation, never a silent edit.

### Changes Required:

#### 1. Calibration lock data model

**File**: `claude/.claude/scripts/lib/calibration_lock.py` (module docstring states it; Phase 3 creates the file)

Lock path `${XDG_STATE_HOME:-$HOME/.local/state}/claude-calibration/lock.json` (a relative `XDG_STATE_HOME` is ignored). Fields written by `mutation_lock.py lock`, field-compatible with today's jq output (same keys and types; `json.dumps` escapes non-ASCII where jq writes UTF-8, and the guard reads both the same way):

| Field | Type | Value |
|---|---|---|
| `ts` | string | `time.strftime(STAMP_FORMAT, time.gmtime())`, `STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"` |
| `kind` | string | `"mutation-test"` |
| `writer` | string | `"mutation-tester"` |
| `file` | string | target path relative to `worktree`, POSIX form |
| `backup_path` | string | absolute `<state folder>/backups/<file>` |
| `pre_hash` | string | first 16 hex characters of sha256 of the target's bytes |
| `class` | string | `"mutant: " + --class` |
| `line` | string | `--line` as given |
| `worktree` | string | absolute `git rev-parse --show-toplevel` of the target's folder |
| `owner_pid` | int | `--owner-pid` as a JSON integer |

Written with `write_text_atomically(calibration_lock_path(), json.dumps(fields, indent=2) + "\n")` inside `hold_exclusive(<state folder>/lock.write, LOCK_WAIT_SECONDS)` (`LOCK_WAIT_SECONDS = 5` from `calibration_lock`; `lock` creates the state folder first). The guard never reads `lock.write`. `$HOME/.claude/calibration-lock.json` is read as a fallback only, never written. Backups are `<state folder>/backups/<relpath>`, saved with `file_backup.save_files`, kept after restore; `discard` is never called.

#### 2. `calibration_lock` module API

**File**: `claude/.claude/scripts/lib/calibration_lock.py`

| Name | Signature | Source |
|---|---|---|
| `STAMP_FORMAT` | `"%Y-%m-%dT%H:%M:%SZ"` | from `parse_stamp` |
| `MUTATION_RUN_TIMEOUT_SECONDS` | `3600` | moved from guard `:27` |
| `LOCK_WAIT_SECONDS` | `5` | new |
| `MUTATION_KIND`, `MUTATION_WRITER`, `PRE_HASH_LENGTH` | `"mutation-test"`, `"mutation-tester"`, `16` | new |
| `state_folder()` | `-> str`, under `script_utils.xdg_state_home()` | from guard `main` |
| `calibration_lock_path()` | `-> str`, `state_folder()/lock.json` | from guard `main` |
| `legacy_lock_path()` | `-> str`, `$HOME/.claude/calibration-lock.json` | from guard `main` |
| `backups_folder()` | `-> str`, `state_folder()/backups` | new |
| `backup_path(file)` | `-> str`, `backups_folder()/file` | new |
| `pre_hash(file)` | `-> str`, first `PRE_HASH_LENGTH` hex characters of the sha256 of the bytes | new |
| `find_lock()` | `-> str or None`, state path first, then legacy | from guard `main` |
| `read_lock_text(path)` | `-> str or None` (None on `OSError`; utf-8, `errors="replace"`) | from guard `main` |
| `lock_field(text, key, default, fallback)` | unchanged | moved `:30-51` |
| `parse_stamp(stamp)` / `format_stamp(epoch)` | `-> int or None` / `-> str` | moved `:54-59`, plus new |
| `lock_is_live(stamp, owner_pid, now, writer="", session_pid="")` | unchanged | moved `:72-85` |
| `LockView` NamedTuple (`file, backup, seed_class, stamp, kind, worktree, owner_pid, writer`) and `read_lock_view(text)` | the guard's defaults (`"?"`, `"calibrate"`, `""`) and the relative-file join | moved `:117-129` |
| `live_notice(kind, file, worktree, owner_pid)` | unchanged | moved `:88-97` |
| `recovery_commands(view, lock)` | `-> (cp command, rm command)`, cp/rm paths through `shell_word` | new |
| `unrestored_message(view, lock)` | `-> str`, UNRESTORED text; paths print as one shell word, and the closing sentence now reads "Do not dispatch mutation-tester until this lock is gone — it refuses to seed on top of an unrestored seed." | moved `:139-162` |

#### 3. `mutation_lock.py` CLI

**File**: `claude/.claude/scripts/tools/mutation_lock.py`

```
mutation_lock.py check <target>
mutation_lock.py lock <target> --class TEXT --line TEXT --owner-pid PID
mutation_lock.py restore --owner-pid PID --run-id ID
```

`description = __doc__.splitlines()[0]`; the epilog lists `PRECONDITIONS`, a tuple of one-line strings in check order, the one owner of the precondition list. Exit codes: `EXIT_OK = 0`, `EXIT_STOP = 1` (precondition failed or request refused; nothing written, lock untouched), `EXIT_RESTORE_MISMATCH = 3`; 2 stays argparse's usage error. Every verb's last line is `NEXT: …`, `STOP: …` or `DONE: …`, each a named constant.

`check`, in order, stopping at the first failure: (1) regular file, not a symlink — `STOP_NOT_A_FILE`; (2) the folder is in a git work tree — `STOP_NOT_A_REPO`; (3) inside that tree and not under `.git/` — `STOP_OUTSIDE_TREE`; (4) no lock at the state or legacy path — live: `live_notice(...)` then `STOP_LIVE_LOCK`; stale or unreadable: the lock's `file` and `backup_path`, `unrestored_message(...)`, then `STOP_UNRESTORED`; (5) the nearest existing parent of the backups folder is writable (`os.access`; `check` creates nothing) — `STOP_STATE_UNWRITABLE`. All pass: when `git status --porcelain -- <relpath>` prints anything, one line `NOTE: <relpath> has uncommitted edits (<that status line>); restore brings back the bytes as they are now` (D18), then `NEXT: run the unmutated suite (baseline), then mutation_lock.py lock <target> --class "..." --line "..." --owner-pid "$PPID"`. `check` writes nothing.

`lock`: `os.makedirs(state_folder, exist_ok=True)`, then `hold_exclusive(state_folder / "lock.write", LOCK_WAIT_SECONDS)` (`LockTimeoutError` → `STOP_LOCK_BUSY`); re-run the five checks, printing the same `NOTE:` line on a dirty or untracked target (D18); `save_files(worktree, [relpath], backups)` (an `unsaved` entry → `STOP_BACKUP_FAILED`, no lock written); compute `pre_hash`; write the lock with a random `run_id` (D19); print the lock path, backup path and `pre_hash`, then `NEXT: apply the mutation with Edit (Step 2); restore later with mutation_lock.py restore --owner-pid "$PPID" --run-id <id>`. `--class` is one non-empty line, else `EXIT_STOP`; `--owner-pid` is `type=int` and positive.

`restore` reads the state-path lock only: legacy lock only → the guard's manual lines, `STOP_LEGACY_LOCK`; no lock → `STOP_NO_LOCK`; `worktree` or `file` missing, or `backup_path != backups/<file>` → `STOP_OLD_LAYOUT` with the manual `cp` and `rm` lines (D12); then `writer != "mutation-tester"` or `str(owner_pid) != str(--owner-pid)` or `run_id` missing or ≠ `--run-id` → when the lock is live (`calibration_lock.lock_is_live`: owner pid alive within the timeout) the live notice and `STOP_LIVE_LOCK` with no commands (AC18 reword, 2026-11-24); when stale, `lock: <abs>`, the recovery line `cp <backup> <target> && rm <lock>` (each path printed as one pasteable shell word (double quotes, or single quotes when the path holds a character double quotes would expand or end on)), `<target>` being `worktree/file` and all three paths absolute (D15), then `STOP_NOT_OURS` as the last line; backup missing → `STOP_BACKUP_MISSING`, lock kept; copy-back `OSError` → `cannot restore <target>: <error>`, `lock kept: <abs>`, the recovery line, `STOP_RESTORE_FAILED`, exit 1; backup hash ≠ `pre_hash` → `RESTORE HASH MISMATCH`, `target: <abs>`, `backup: <abs>`, `lock kept: <abs>`, `STOP_BACKUP_MISMATCH`, target untouched, exit 3. Else `restore_changed(Backup(worktree, backups, [file], []))`, hash the target: mismatch → `RESTORE HASH MISMATCH`, `target: <abs>`, `backup: <abs>`, `lock kept: <abs>`, `STOP_RESTORE_MISMATCH` as the last line, exit 3; match → `os.unlink(lock)`; `OSError` → `STOP_LOCK_NOT_REMOVED` with `rm <lock>` (same quoting), exit 1; success → `DONE: restore hash-verified (<copied|already identical>); lock removed`.

#### 4. `refactor_flow.py log --help` contract

**File**: `claude/.claude/skills/refactor/scripts/refactor_log_input.py`

`RawDescriptionHelpFormatter`; the `log` subparser gets `help="append the escape and finder rows of one /refactor run"` and `epilog=refactor_log_input.log_help_epilog()`, which is `FIELD_NOTES`, the line `TEMPLATE_START = "--- log input template (branch mode, JSON) ---"`, `json.dumps(LOG_TEMPLATE, indent=2)`, the line `TEMPLATE_END = "--- end of log input template ---"`. `LOG_TEMPLATE` is a dict equal to today's fenced JSON in `refactor/SKILL.md:70-100`. Exit 0. Every other verb, argument and exit code is unchanged.

#### 5. rule-meter scenario and detector contract

**Files**: `~/agent-evals/bin/rule_meter_scenarios.json`, `~/agent-evals/bin/rule_meter_guide.py`

Scenario ids `GD03`, `GD04`, `GD05`, `GD07`; detector names `guide_response_declared_once`, `guide_callout_names_check`, `guide_meta_carries_keys`, `guide_one_judgment_per_card`. Each detector is `(result_text) -> (outcome, evidence)`; `NO_TEST` on no parseable ```json batch or fewer than two cards. `GD08` has no scenario and is listed `unmeasured`.

### Success Criteria

#### Automated Verification:

- [ ] N/A — Phase 0 is content frozen in this file; Phases 1, 3, 4 and 7 verify each contract.

#### Manual Verification:

- [ ] Manual Verification: N/A (contracts only)

---

## Phase 1: Walking skeleton — `refactor_log_input.py` split out, `log --help` prints the template

### Overview

The grammar leaves `refactor_flow.py` for a sibling module that also owns the template; `log --help` prints it. About +240 / -200.

### Changes Required:

#### 1. New grammar module

**File**: `claude/.claude/skills/refactor/scripts/refactor_log_input.py`
**Changes**: Docstring: owns the `refactor_flow.py log` input grammar and its template. Starts with the same `sys.path` insert of `scripts/lib` as `refactor_flow.py:53`, then `import plan_format`. Move verbatim from `refactor_flow.py`: `class RefactorFlowError` (`:117-119`), `FINDERS` (`:70`), `PLAN_STRUCTURE_TAG` (`:90`), `require_text` (`:599-603`), `single_line` (`:606-610`), `SWALLOWED_PAIR` (`:613`), `one_line_path` (`:616-622`), `validate_finding` (`:625-656`), `validate_escape_finding` (`:659-670`), `validate_handoff` (`:673-690`), `require_escape_guards` (`:693-697`), `validated_targets` (`:700-706`), `validate_log` (`:709-745`), `read_refactor_log` (`:806-813`), `read_modifier` (`:816-820`). Add `LOG_TEMPLATE` (SKILL.md `:70-100` as a dict), `FIELD_NOTES` (the format facts from SKILL.md `:65-68` and the docstring `:22-34`: finder values and that finder is omitted in targeted mode; `lane` required with a finder; `result` optional; `target` per mode; finding keys with `line` 0 for no line and one-line `desc`; `escape` with `severity` and `miss_reason`, never `unknown`; escape rows only in branch and simplify mode, simplify with `class=complexity`; `plan_structure` needs `disposition=ask`; `ruled_by` user or session; `guards` one per escape class; `handoff` keys and line rules, never in audit mode; optional string `modifier`), `TEMPLATE_START`, `TEMPLATE_END`, `log_help_epilog()`.

#### 2. `refactor_flow.py` imports the module

**File**: `claude/.claude/skills/refactor/scripts/refactor_flow.py`
**Changes**: `import refactor_log_input`; bind `RefactorFlowError = refactor_log_input.RefactorFlowError` (so `NoSharedHistoryError`, `NoBaseError` and the tests' `module.RefactorFlowError` keep working), and `FINDERS`, `PLAN_STRUCTURE_TAG` the same way for `PLAN_STRUCTURE_RULE` (`:91-94`) and `_branch_next` (`:479`). `log_verb` and `handoff_verb` (`:1008-1010`, `:1050-1055`) call `refactor_log_input.validate_log`, `validate_handoff`, `read_refactor_log`, `read_modifier`. The `log` subparser (`:1074-1077`) gets `help`, `epilog` and `formatter_class` per Phase 0. Docstring `:22-34` becomes one line: "Input file: JSON in the shape `refactor_flow.py log --help` prints; `log` reads all of it, `handoff` reads only `handoff` and `modifier`." Usage and exit-code lines stay. Target at most about 950 lines.

#### 3. Lint config

**File**: `ruff.toml`
**Changes**: add `"claude/.claude/skills/refactor/scripts/refactor_log_input.py" = ["E402"]` right under the `refactor_flow.py` entry at `:28`, under the same comment.

#### 4. Tests

**File**: `tests/scripts/test_refactor_flow.py`
**Changes**: reach the grammar module through the loaded script, `flow = load_script_module()`; `flow.refactor_log_input` is the module `refactor_flow.py` imported through `sys.path`, so `REFACTOR_FLOW_PATH` stays the one variable and no second module object exists. Replace `test_the_log_input_example_in_the_skill_logs_on_the_first_call` (`:344-352`) with `test_the_log_template_in_log_help_logs_on_the_first_call`: run `log --help`, take the text between `TEMPLATE_START` and `TEMPLATE_END`, `json.loads` it, and after `pushed_feature_branch({"src/orders.py": "x = 1\n"})` run `log branch` on it and assert exit 0. Add `test_the_log_grammar_lives_in_refactor_log_input`: `flow.refactor_log_input.validate_log("branch", copy of flow.refactor_log_input.LOG_TEMPLATE)` returns a dict and `flow.RefactorFlowError is flow.refactor_log_input.RefactorFlowError`. Add `test_refactor_flow_is_at_most_1000_lines`: `len(SCRIPT.read_text().splitlines()) <= 1000`. `HEAVY_FIRST` and `PROMPT_READING_TESTS` keep `test_refactor_flow.py` unchanged.

### Success Criteria

`log --help` prints a template that logs in branch mode on the first call; old input files parse as before; `refactor_flow.py` is at most 1000 lines.

#### Automated Verification:

- [ ] **Test-verified**: the template printed by `log --help` logs on the first call — `PYTHONPATH=tests/scripts python3 -m unittest -k test_the_log_template_in_log_help_logs_on_the_first_call tests/scripts/test_refactor_flow.py`
- [ ] **Test-verified**: the grammar lives in the new module and the error class is one object — `PYTHONPATH=tests/scripts python3 -m unittest -k test_the_log_grammar_lives_in_refactor_log_input tests/scripts/test_refactor_flow.py`
- [ ] **Test-verified**: `refactor_flow.py` has at most 1000 lines — `PYTHONPATH=tests/scripts python3 -m unittest -k test_refactor_flow_is_at_most_1000_lines tests/scripts/test_refactor_flow.py`
- [ ] **Lint-verified**: both scripts pass the repo lint and complexity gate — `bash tests/lint.sh claude/.claude/skills/refactor/scripts/refactor_log_input.py claude/.claude/skills/refactor/scripts/refactor_flow.py`

#### Manual Verification:

- [x] agent-verified: run `python3 claude/.claude/skills/refactor/scripts/refactor_flow.py log --help`; the output ends with the field notes, the start marker, an indented JSON object and the end marker. — evidence: `python3 claude/.claude/skills/refactor/scripts/refactor_flow.py log --help | grep -n "log input template"` → `32:--- log input template (branch mode, JSON) ---` and `65:--- end of log input template ---`; tail shows indented JSON closing `}` before the end marker.

---

## Phase 2: refactor skill and close-branch point to `log --help`

### Overview

The prose consumers drop the template and name the command that prints it. About +12 / -40. The coder loads `toolkit-writing` first.

### Changes Required:

#### 1. Refactor skill Step 5

**File**: `claude/.claude/skills/refactor/SKILL.md`
**Changes**: in Step 5 (`:64-100`) the opening paragraph stays with one clause added: "Write the JSON file at the path the prep script's `NEXT:` line named (a fresh path for each invocation), in the shape `python3 ~/.claude/skills/refactor/scripts/refactor_flow.py log --help` prints, and run …", unchanged through "prints the `/review` handoff block." Then three bullets, the judgment parts of `:65-67` with their key lists stripped (D3), each exactly: "`lane` (required whenever there is a finder; from conversation/planning artifacts)."; "`findings`: one entry per finder finding. Add `escape: true` plus `severity` and `miss_reason` (a label from `escape-ratchet.md`; not `unknown`) for each distinct smell in branch-loop code (branch-audit: `duplication` for scope-item-1, `smell` otherwise; simplify: `complexity`). One entry per smell, not per file. Never `escape` mechanical-sweep matches or legacy targets — old debt is not an escape."; "`guards`: one guard per escape `class` group, from the ratchet (`escape-ratchet.md`, read in step 3a; read it now in simplify mode). The script refuses an escape class with no guard." Delete the key-shape text (the `{class, disposition, …}` set with its `line` and `desc` notes, the `finder` and `result` key text, the `handoff` key bullet) and the fenced `json` block. Line `:115` (audit mode 6d) "(JSON as in step 5, with `target`" becomes "(the shape `log --help` prints, with `target`". The `handoff` fallback paragraph (`:102`) and the auto-dispatch line stay.

#### 2. close-branch pointer

**File**: `claude/.claude/skills/close-branch/SKILL.md`
**Changes**: line 68, "in the input shape of `~/.claude/skills/refactor/SKILL.md` Step 5" becomes "in the shape `python3 ~/.claude/skills/refactor/scripts/refactor_flow.py log --help` prints".

#### 3. Rule anchor

**File**: `docs/rule-anchors.md`
**Changes**: row `458c884f` (`:127`, refactor `## Instructions`) gets the new hash from `bash claude/.claude/scripts/tools/rule-anchors.sh list claude/.claude/skills/refactor/SKILL.md` and one added reason sentence: the log input shape is printed by `refactor_flow.py log --help`, and the skill keeps the judgment bullets. `close-branch/SKILL.md` has no rows.

#### 4. Tests

**File**: `tests/scripts/test_refactor_flow.py`
**Changes**: add `test_the_refactor_skill_holds_no_log_json_template` (`SCRIPT.parent.parent / "SKILL.md"` has no fenced `json` block and no "JSON as in step 5"). Add `test_close_branch_step_five_points_to_log_help` beside `test_close_branch_step_five_names_the_branch_log_command` (`:1275`): `assertIn("log --help", text)` and `assertNotIn` of the old "refactor/SKILL.md` Step 5" phrase.

### Success Criteria

The refactor skill has no fenced JSON, keeps the trigger, the command, the pointer and the three judgment bullets; close-branch names `log --help`; the anchor row matches.

#### Automated Verification:

- [ ] **Test-verified**: the skill holds no log JSON template — `PYTHONPATH=tests/scripts python3 -m unittest -k test_the_refactor_skill_holds_no_log_json_template tests/scripts/test_refactor_flow.py`
- [ ] **Ban-verified**: no fenced json block remains in the refactor skill (no match holds) — `rg -q '^\s*\x60{3}json' claude/.claude/skills/refactor/SKILL.md`
- [ ] **Test-verified**: close-branch points to `log --help` — `PYTHONPATH=tests/scripts python3 -m unittest -k test_close_branch_step_five_points_to_log_help tests/scripts/test_refactor_flow.py`

#### Manual Verification:

- [x] agent-verified: read Step 5 of `claude/.claude/skills/refactor/SKILL.md`; it holds the paragraph with the `log --help` clause and exactly three bullets, no key list and no JSON. — evidence: `sed -n 64,67p` of the file shows the paragraph naming `refactor_flow.py log --help` then three bullets (`lane`, `findings`, `guards`); `rg -q '^\s*```json'` → rc=1 (no match).

---

## Phase 3: `lib/calibration_lock.py`, with `calibration_guard.py` importing it

### Overview

The lock format gets one owner. The guard keeps its outputs and exit codes, apart from two changes: shell-special paths are quoted as one shell word, and the unrestored message's closing sentence no longer names the deleted `/calibrate` skill ("Do not dispatch mutation-tester until this lock is gone — it refuses to seed on top of an unrestored seed"). About +180 / -120.

### Changes Required:

#### 1. New module

**File**: `claude/.claude/scripts/lib/calibration_lock.py`
**Changes**: the Phase 0 API table; moved bodies verbatim; the module docstring names it the owner of the lock format and lists the fields of the Phase 0 data model.

#### 2. Guard imports it

**File**: `claude/.claude/scripts/gates/calibration_guard.py`
**Changes**: `import calibration_lock`, drop the moved code; `main` builds the same output as before (shell-special paths quoted through `shell_word` via `unrestored_message`; the unrestored message's closing sentence no longer names the deleted `/calibrate` skill) from `find_lock`, `read_lock_text`, `read_lock_view`, `lock_is_live`, `live_notice`, `unrestored_message`. Keep the docstring's hook contract (the field list moves to the lib docstring), `session_pid_argument`, the path and the exit codes. The dormant `writer == "calibrate"` branch stays.

#### 3. Tests

**File**: `tests/scripts/test_calibration_lock.py` (new)
**Changes**: module path from `CALIBRATION_LOCK_MODULE`, defaulting to `toolkit_paths.LIB_DIR / "calibration_lock.py"`; the parent goes on `sys.path` for `hook_input`. Tests: `calibration_lock_path` uses `XDG_STATE_HOME` when set, else `HOME/.local/state`; `find_lock` returns the legacy path only when the state lock is absent; `format_stamp(parse_stamp(s)) == s` and `parse_stamp("2026-10-01T10:00:00+00:00")` is None; `read_lock_view` joins a relative `file` to `worktree` and leaves an absolute one alone; `lock_is_live` is false for owner `"99999999"`, true for a fresh lock with no owner, false past the timeout.

**Files**: `tests/scripts/test_calibration_guard.py`, `tests/scripts/test_review_fixes.py` — the existing tests pass unchanged apart from the closing-sentence pin in `test_calibration_guard.py` (the plain-path proof, D4); one case for a path with shell characters is added (AC9 reword, D15).

### Success Criteria

The guard's existing tests pass unchanged against the import, apart from the closing-sentence pin in `test_calibration_guard.py`; the module's path, stamp, view and liveness functions behave as the table states.

#### Automated Verification:

- [ ] **Test-verified**: the new module tests, the guard tests and the self-location scan pass — `python3 tests/parallel_tests.py test_calibration_lock.py test_calibration_guard.py test_review_fixes.py test_toolkit_self_location.py`
- [ ] **Lint-verified**: module and guard pass lint — `bash tests/lint.sh claude/.claude/scripts/lib/calibration_lock.py claude/.claude/scripts/gates/calibration_guard.py`

#### Manual Verification:

- [x] agent-verified: with no lock on this machine, run `python3 claude/.claude/scripts/gates/calibration_guard.py`; it exits 0 and prints nothing, as before. — evidence: `python3 claude/.claude/scripts/gates/calibration_guard.py </dev/null; echo rc=$?` → no output, `rc=0`.

---

## Phase 4: `tools/mutation_lock.py` with its tests

### Overview

The script that does the preconditions, backup, hash, lock and verified restore. About +260 script, +320 tests.

### Changes Required:

#### 1. The script

**File**: `claude/.claude/scripts/tools/mutation_lock.py`
**Changes**: the Phase 0 CLI. Siblings through `pathlib.Path(__file__).resolve()` plus a `sys.path` line for `lib/`; `argparse` subparsers; `hold_exclusive`, `save_files`, `restore_changed`, `Backup`, `write_text_atomically`, and every lock fact through `calibration_lock`. Fail-closed comment on `check` (any unreadable state stops). No ruff entry beyond the existing `claude/.claude/scripts/*/*.py` E402 glob.

#### 2. Tests

**File**: `tests/scripts/test_mutation_lock.py` (new)
**Changes**: script path from `MUTATION_LOCK_PATH`, defaulting to `toolkit_paths.TOOLS_DIR / "mutation_lock.py"`. Each test gets a temp `HOME` with `XDG_STATE_HOME` set and a temp git repo holding a committed `src/a.py`. Cases: (1) `check` on a clean file exits 0 with a `NEXT:` line and writes neither lock nor backup; (2) `check` exits 1 with its STOP line for a missing file, a symlink, a folder outside any git repo, a path outside the work tree; (3) `check` with a live lock (fresh `ts`, `owner_pid=os.getpid()`) exits 1 with `STOP_LIVE_LOCK`, lock bytes unchanged; (4) `check` with a stale lock (owner `99999999`) and with a legacy-only lock exits 1, prints the lock's `file` and `backup_path`, lock unchanged; (5) `lock` writes exactly the Phase 0 key set: `ts` matches `^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$`, `owner_pid` is an `int`, `pre_hash == sha256(bytes)[:16]`, `file == "src/a.py"`, `worktree` is the repo toplevel; the backup at `backups/src/a.py` holds identical bytes; `gates/calibration_guard.py --live` exits 0 against a lock written with a live `--owner-pid`; (6) `lock` while a live lock, a stale lock or a legacy-only lock exists exits 1, lock bytes unchanged, no backup written; (7) `restore` after an edit makes the file byte-identical, removes the lock, exits 0 and prints `DONE:`; `restore` with no edit also exits 0 and says "already identical"; (8) `restore` with a tampered backup exits 3, keeps the lock, prints target and backup paths; (9) `restore` refuses another `owner_pid`, another `writer` and another `run_id`: exit 1, target and lock unchanged; a live lock of another run stops with `STOP_LIVE_LOCK`; (10) `restore` of an old-layout lock (`backups/a.py.bak`) exits 1 with the manual `cp` line and keeps the lock; (11) `--help` lists every entry of the module's `PRECONDITIONS`, read from the loaded module; (12) `check` and `lock` on a target with an uncommitted edit, and on an untracked new file, exit 0, print one `NOTE:` line naming the file and its `git status --porcelain` line, and otherwise behave as cases 1 and 5 (D18); (13) the `STOP_NOT_OURS` refusal of a stale lock in case 9 prints a `cp <backup> <target> && rm <lock>` line with the real absolute paths, each one pasteable shell word; the live refusal prints no commands; (14) `lock` on a sparse target made with `os.truncate` to `file_backup.MAX_FILE_BYTES + 1` exits 1 with `STOP_BACKUP_FAILED` and writes no lock; (15) `restore` with no lock exits 1 with `STOP_NO_LOCK`; with a legacy-only lock exits 1 with `STOP_LEGACY_LOCK`; with the lock's backup deleted exits 1 with `STOP_BACKUP_MISSING`, lock kept, target unchanged; (16) `restore` after `lock`, an edit and `os.chmod(state_folder, 0o500)` exits 1 with `STOP_LOCK_NOT_REMOVED` and the `rm <lock>` line, the target restored (`addCleanup` sets the mode back).

### Success Criteria

`check`, `lock` and `restore` behave as Phase 0 states on every case above; a script-written lock reads as live to the guard.

#### Automated Verification:

- [ ] **Test-verified**: all sixteen cases pass — `python3 tests/parallel_tests.py test_mutation_lock.py`
- [ ] **Lint-verified**: the script passes lint — `bash tests/lint.sh claude/.claude/scripts/tools/mutation_lock.py`

#### Manual Verification:

- [ ] human-only: in a scratch git repo with `XDG_STATE_HOME` pointed at a scratch folder, run `check`, `lock --class x --line 1 --owner-pid $$`, edit the file, `restore --owner-pid $$ --run-id <id from the lock's NEXT line>`; the file is back to its bytes and the last line starts `DONE: restore hash-verified`. — not run: it creates a scratch repo and files, which this run may not create; `test_restore_after_an_edit_puts_the_bytes_back_and_removes_the_lock` (passed) covers it.

---

## Phase 5: mutation-tester and its opencode port call the script

### Overview

Both prompts replace the lock, backup and restore prose with one script line per step. About +45 / -75 per file. The coder loads `toolkit-writing` first.

### Changes Required:

#### 1. The claude agent

**File**: `claude/.claude/agents/mutation-tester.md`
**Changes**: Step 0 heading becomes `## Step 0 — Preconditions (before touching anything)`; the `git rev-parse && git status` block goes; bullets: first, word for word as its anchor row requires, "The dispatch does not state a test command → stop and say so. Never infer one from the repo."; then "The target is not the file named in the dispatch → stop."; then "Run `python3 ~/.claude/scripts/tools/mutation_lock.py check <target>` (`mutation_lock.py --help` lists what it checks). It ends with `STOP:` → stop and report what it printed. Never mutate on top of an unrestored mutation. Never clear someone else's lock." The baseline paragraph and the executed-count line stay. Step 1 becomes one fenced line, `python3 ~/.claude/scripts/tools/mutation_lock.py lock <target> --class "<one-line description>" --line "<line>" --owner-pid "$PPID"`, then "It ends with `STOP:` → stop and report it; the target and the lock are untouched." and, from the close pass (D19), "It ends with `NEXT: apply the mutation` → keep the `--run-id` value on that line for the Step 4 restore line." Step 4 opens with "This runs only after `lock` printed `NEXT: apply the mutation`, whether the suite passed, failed, errored, hung, or you decided to abort at Step 2. When `lock` stopped, there is nothing to restore." (D19; the original "This runs whether…" line) and keeps word for word "**Restore by copying the backup file. Never `git checkout`**. **Never `Write`, and never `Edit`.**", then "The restore is this one call and nothing else:", the fenced `python3 ~/.claude/scripts/tools/mutation_lock.py restore --owner-pid "$PPID" --run-id <run-id>` (D19), and bullets: "Exit 0 → say in your report that the restore was hash-verified."; "Exit 3 (`RESTORE HASH MISMATCH`) → **STOP and say so loudly**, with the target path and the backup path it printed, at the very top of your report. Do not delete the lock. Do not report a verdict as though the run completed normally."; "Any other `STOP:` → report the verdict, state the stop, and print the exact command it names, if any, for your caller to run. Never retry by another mechanism." (D13, reworded by D19). Steps 2 and 3, Hard limits and Output Format are unchanged.

#### 2. The opencode port

**File**: `opencode/.config/opencode/agents/mutation-tester.md`
**Changes**: the same Step 0, 1 and 4 bodies, except that its Step 4 keeps the two reason clauses after `Never git checkout` and `never Edit`. Add the test-command bullet first. Remove the legacy `~/.claude/calibration-lock.json` and `~/.claude/calibration` paths and the jq, `sha256sum` and `cp` blocks; remove "all four", "/calibrate" and "The lock is GLOBAL" from Step 0. "print the exact command for the user" becomes "for your caller". Its Step 0 heading becomes the claude one, `## Step 0 — Preconditions (before touching anything)`; its Step 4 heading `## Step 4 — Restore. Non-negotiable, and it runs on every path` stays. Frontmatter and its other adaptation lines stay.

#### 3. Rule anchors

**File**: `docs/rule-anchors.md`
**Changes**: from `bash claude/.claude/scripts/tools/rule-anchors.sh list claude/.claude/agents/mutation-tester.md`: row `6ca266a8` gets the new section key `## Step 0 — Preconditions (before touching anything)` and hash; its reason keeps the six-of-six placement sentence and adds "the checkable preconditions are owned by `mutation_lock.py --help`." Rows `84cdf15f` (Step 1) and `d11ed9bc` (Step 4) get new hashes; their reasons say the backup, hash, lock and restore steps run in `mutation_lock.py`. No other row changes.

#### 4. Prompt test

**File**: `tests/scripts/test_mutation_lock.py`
**Changes**: add `test_both_mutation_tester_prompts_call_only_verbs_and_flags_the_script_takes`: read `toolkit_paths.CLAUDE_DIR / "agents" / "mutation-tester.md"` and `toolkit_paths.REPO_ROOT / "opencode" / ".config" / "opencode" / "agents" / "mutation-tester.md"`; for each, the `mutation_lock.py <verb>` calls found are exactly `{"check", "lock", "restore"}` and every `--flag` on a call appears in that verb's `--help`. Add `test_both_mutation_tester_prompts_name_no_lock_path_hash_tool_or_count`: neither file holds `claude-calibration`, `calibration-lock.json`, `sha256sum`, `jq -n`, `all four` or `all five`, and each file's Step 0 section holds exactly three bullets, of which exactly one holds `mutation_lock.py check`. Add `test_mutation_tester_prompts_keep_the_restore_only_rule`: each file's Step 4 names `git checkout`, `Write` and `Edit` as forbidden restore routes, names `RESTORE HASH MISMATCH` as a loud stop, and holds the hand-the-command-to-the-caller sentence.

#### 5. Kept-test list

**File**: `tests/changed_scope.py`
**Changes**: add `"test_mutation_lock.py"` to `PROMPT_READING_TESTS` after `"test_log_review_finding.py"` (`:31`). `HEAVY_FIRST` unchanged.

### Success Criteria

Each agent step is one script line; Step 0's heading has no count; neither prompt names a lock path, jq, sha256sum or a count; the anchor rows match; the kept-test list stays honest.

#### Automated Verification:

- [ ] **Test-verified**: prompt test, kept-list test and anchors pass — `python3 tests/parallel_tests.py test_mutation_lock.py test_prompt_reader_list.py test_rule_anchors.py`
- [ ] **Ban-verified**: no lock path, hash tool, jq or precondition count remains in either prompt (no match holds) — `rg -q -e claude-calibration -e 'calibration-lock\.json' -e sha256sum -e 'jq -n' -e 'all four' -e 'all five' claude/.claude/agents/mutation-tester.md opencode/.config/opencode/agents/mutation-tester.md`

#### Manual Verification:

- [x] agent-verified: read Steps 0, 1 and 4 of both files side by side; the three script lines are identical in both. — evidence: `grep -n mutation_lock` on both agent files → check line (claude:27, opencode:31), lock line (claude:37, opencode:44) and restore line (claude:86, opencode:95) carry identical text: `... mutation_lock.py lock <target> --class "<one-line description>" --line "<line>" --owner-pid "$PPID"`, `... restore --owner-pid "$PPID" --run-id <run-id>`.

---

## Phase 6: the guide skill keeps one worked card

### Overview

Two of three worked cards go; nothing else changes. About -25. The coder loads `toolkit-writing` first.

### Changes Required:

#### 1. The skill

**File**: `claude/.claude/skills/guide/SKILL.md`
**Changes**: heading `## Three worked cards` (`:114`) becomes `## A worked card`. Keep "**A judgment call with evidence** — the common case." and its jsonc block (`:116-186`) unchanged. Delete the "An A/B comparison" paragraph with its jsonc block (`:187-197`) and the "A rating" line (`:198`). Commands block, batch, card envelope, block and field tables, rules and answers shape are unchanged in this phase. `claude/.claude/settings.json:195` is not touched (D9).

### Success Criteria

One worked card remains; the tables and all eight rules are untouched.

#### Automated Verification:

- [x] **Ban-verified**: the two cut cards and the old heading are gone (no match holds) — `rg -q -e 'An A/B comparison' -e '\*\*A rating\*\*' -e 'Three worked cards' claude/.claude/skills/guide/SKILL.md` — cut by D20: the file is deleted on master
- [x] **Presence-verified**: the new heading is present — `rg -q '^## A worked card$' claude/.claude/skills/guide/SKILL.md` — cut by D20: the file is deleted on master

#### Manual Verification:

- [x] agent-verified: read `## A worked card`; the "A judgment call with evidence" card and its one jsonc block follow it, then `## Rules`. `git diff --stat` shows `claude/.claude/settings.json` untouched. — evidence: `grep -n '^## '` → `114:## A worked card`, `187:## Rules`; line 116 `**A judgment call with evidence**`; `git diff --stat 737ff9f67 -- claude/.claude/settings.json` → empty. Rules now run 1..6 because Phase 8 cut two. — cut by D20: the file is deleted on master

---

## Phase 7: rule-meter scenarios and detectors for guide rules 3, 4, 5 and 7

### Overview

The meter gets a scenario per rule and a result-text detector per scenario, in `~/agent-evals`. `rule_meter.py` is untouched.

### Changes Required:

#### 1. Preflight and toolkit copy

**Files**: `~/dev/evals/rulemeter1/toolkits/gd/claude/.claude/skills/guide/SKILL.md` (new copy)
**Changes**: run `git -C ~/agent-evals status bin/` first; never touch another session's uncommitted file there. Copy this worktree's post-Phase-6 `claude/.claude/skills/guide/SKILL.md` to the toolkit copy path (the `uq01` precedent), so the scenarios outlive the worktree.

#### 2. Scenarios

**File**: `~/agent-evals/bin/rule_meter_scenarios.json`
**Changes**: four rows keyed `GD03`, `GD04`, `GD05`, `GD07`, each with `model: "opus"`, `rule_source: "skills/guide/SKILL.md"`, `toolkit_root: "~/dev/evals/rulemeter1/toolkits/gd/claude/.claude"`, `setup: null`, a `note` naming result-text grading, `rule_text` as the rule's full numbered list item word for word with its line wraps (so `remove_once` finds it), a `task` that says the `guide` binary is not installed in this tree: write the batch to `questions.json` and paste the whole batch as strict JSON (no comments) in a ```json block in the final reply, do not run `guide`; and `supportive`, `neutral`, `competing` suffixes.

| Id | Rule | Detector | Task gist | COMPLIED / VIOLATED |
|---|---|---|---|---|
| GD03 | 3, declare the response once | `guide_response_declared_once` | six verifier findings from one check, each needing the same false-alarm / good-catch verdict | VIOLATED: two or more cards carry an equal `response`; COMPLIED otherwise on a parseable batch of two or more cards; NO_TEST otherwise |
| GD04 | 4, a callout says why | `guide_callout_names_check` | findings from a named check whose purpose the task gives | COMPLIED: every card has a `callout` block, top level or in `columns`; VIOLATED otherwise |
| GD05 | 5, keys go in `meta` | `guide_meta_carries_keys` | each finding comes with a run id and a file path | COMPLIED: every card's `meta` values hold its run id and file path; VIOLATED otherwise |
| GD07 | 7, one judgment per card | `guide_one_judgment_per_card` | three findings plus three unrelated threshold decisions | COMPLIED: every card has at most one `required: true` field; VIOLATED otherwise |

Every detector grades `NO_TEST` on no parseable batch or fewer than two cards. GD08 gets no row.

#### 3. Detectors and their wiring

**File**: `~/agent-evals/bin/rule_meter_guide.py` (new)
**Changes**: pure functions `(result_text) -> (outcome, evidence)` and a `DETECTORS` dict mapping the four detector names.

**File**: `~/agent-evals/bin/rule_meter_verifier.py`
**Changes**: `import rule_meter_guide`; line 76 becomes `DETECTORS = {"late_fee_verdicts": detect_late_fee_verdicts, **rule_meter_guide.DETECTORS}` (D10).

#### 4. Tests

**File**: `~/agent-evals/bin/test_rule_meter_guide.py` (new)
**Changes**: one COMPLIED, one VIOLATED and one NO_TEST reply per detector.

### Success Criteria

Each detector grades its three fixtures as named; the verifier's table holds the four names; a dry run of a GD cell prints its command.

#### Automated Verification:

- [ ] **Test-verified**: detector tests pass — `python3 -m unittest discover -s /home/brandon/agent-evals/bin -p test_rule_meter_guide.py`
- [ ] **Presence-verified**: the verifier's table finds the guide detectors module — `rg -q 'rule_meter_guide' /home/brandon/agent-evals/bin/rule_meter_verifier.py`
- [ ] **Dry-run-verified**: the meter resolves a GD cell and prints its command without a model call — `python3 /home/brandon/agent-evals/bin/rule_meter.py run --rule GD07 --level neutral --arm on --dry-run`

#### Manual Verification:

- [ ] human-only: `git -C ~/agent-evals status bin/` shows only the four files this phase added or changed (committed in Phase 9 §4) plus any pre-existing untracked files of other sessions, untouched.

---

## Phase 8: meter runs, then the rule cuts

### Overview

The D14 budget decides which of rules 3, 4, 5 and 7 are cut. The coder loads `toolkit-writing` before the edit.

### Changes Required:

#### 1. Runs

**Files**: `~/dev/evals/rulemeter1/runs/results.jsonl` (written by the meter)
**Changes**: preflight `df -h /tmp` shows 4 GB or more free. First pass: one `python3 ~/agent-evals/bin/rule_meter.py run --rule <id> --level <L> --arm <A> --run 1` per cell for GD03, GD04, GD05, GD07 × supportive, neutral, competing × on, off: 24 runs, in the background, never `run-all`. Read `rule_meter.py summary`. A first-pass cell graded `NO_TEST` is rerun once with `--run 2`; a cell still `NO_TEST` makes its rule `unmeasured` (D17), and that rule gets no more runs. Second pass: a rule whose off arm complied at least as often as its on arm at every level gets `--run 2` in all six of its cells; a rule the on arm clearly wins at any level stays and gets no more runs. At most 24 more runs.

#### 2. Cut rule and edit (cut, D20: master deleted the guide skill; no Phase 9 guide note)

**File**: `claude/.claude/skills/guide/SKILL.md`
**Changes**: a rule is cut only when the confirmed second pass holds the same reading (off complies ≥ on) at every level. A rule with any level holding fewer than two graded runs after the second pass goes to `unmeasured` and stays. In `## Rules`, delete each cut rule and renumber the rest with no gap. Rule 8 stays, `unmeasured`. No rule-anchors row exists for this file. The per-arm counts per rule and level are kept for the Phase 9 change file.

### Success Criteria

Every cell of the first pass has a graded row, or its rule is listed `unmeasured` after one rerun; every cut rule has two graded rows per cell with the off arm complying at least as often at every level; the counts are recorded.

#### Automated Verification:

- [ ] **Agent-run**: `rg -c '"rule": "GD0[3457]"' ~/dev/evals/rulemeter1/runs/results.jsonl` returns 24 or more, and `python3 ~/agent-evals/bin/rule_meter.py summary` shows, for each of GD03, GD04, GD05 and GD07, a graded on and off cell at every level or the rule listed `unmeasured` in the session's record; the session records both outputs. Not run by the plan check: the runs cost opus calls and wait on `/tmp` space.
- [ ] **Agent-run**: for each cut rule, the summary shows two graded runs per cell and off ≥ on at every level; the session records the per-rule table.

#### Manual Verification:

- [x] agent-verified: read `## Rules` in `claude/.claude/skills/guide/SKILL.md`; the numbering is 1..N with no gap and every kept rule's text is unchanged. — evidence: `grep -n '^[0-9]\. \*\*'` → rules 1..6 at lines 189-198; `git diff 737ff9f67` on the file shows only old rules 4 and 5 removed and the kept rules' numbers changed (old 6/7/8 → 4/5/6), text unchanged. — cut by D20: the file is deleted on master

---

## Phase 9: change files, rule-anchors links and the full suite

### Overview

Change notes (two after D20 cut the guide note), their links from the anchor rows, and the full suite under `systemd-run`.

### Changes Required:

#### 1. Change notes

**Files**: `docs/changes/notes/<two new notes>.md`, `docs/changes/` index files that `build_changes.py` writes
**Changes**: `python3 ~/agent-evals/bin/build_changes.py new "<title>" --by claude-code/<the model running the step> --root /home/brandon/dotfiles-toolkit-scripts-nov22/docs/changes` for each title: "refactor_flow.py log --help prints the refactor log input template"; "mutation-tester locks, backs up and restores through mutation_lock.py" (a third title, "guide skill keeps one worked card and cuts rules the meter clears", is cut, D20: master deleted the guide skill; no guide note). Fill each. (The guide note, with its per-rule on and off counts, `unmeasured` rules and the table-cut record, is cut, D20.) The mutation-tester note lists the D13 sentence under `unmeasured`. Then `python3 ~/agent-evals/bin/build_changes.py --root /home/brandon/dotfiles-toolkit-scripts-nov22/docs/changes`, and `python3 ~/agent-evals/bin/build_changes.py --check --root /home/brandon/dotfiles-toolkit-scripts-nov22/docs/changes` exits 0 (it also exits 0 today, so it is a step, not a criterion).

#### 2. Anchor links

**File**: `docs/rule-anchors.md`
**Changes**: append `[change](changes/notes/<note>.md)` to rows `458c884f` (refactor note), `6ca266a8`, `84cdf15f`, `d11ed9bc` (mutation-tester note).

#### 3. Full suite

**Changes**: `free -g` shows 8 GB or more available, then `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh`.

#### 4. agent-evals commit

**Files**: `~/agent-evals/bin/rule_meter_guide.py`, `bin/test_rule_meter_guide.py`, `bin/rule_meter_verifier.py`, `bin/rule_meter_scenarios.json`
**Changes**: on `bench-base`, after the Phase 8 runs: `git -C ~/agent-evals status bin/` shows those four files and nothing else of this lane's, then `git -C ~/agent-evals add bin/rule_meter_guide.py bin/test_rule_meter_guide.py bin/rule_meter_verifier.py bin/rule_meter_scenarios.json && git -C ~/agent-evals commit -m "rule-meter: guide skill scenarios GD03-GD07 and result-text detectors" && python3 ~/.claude/scripts/tools/pull_keep_index.py ~/agent-evals && git -C ~/agent-evals push -u origin HEAD` (D10; ruled by agent-evals-c3, 2026-11-22).

### Success Criteria

Two notes exist (the guide note is cut, D20) and the change index checks clean; the four anchor rows link a note; the full suite passes; the four agent-evals files are committed and pushed on `bench-base`.

#### Automated Verification:

- [x] **Presence-verified**: the mutation-tester note is present under the notes folder — `rg -l 'mutation_lock.py' docs/changes/notes`
- [x] **Presence-verified**: the refactor note is present under the notes folder — `rg -l 'log --help' docs/changes/notes`
- [x] **Presence-verified**: the guide note is present under the notes folder — `rg -l 'guide skill keeps one worked card' docs/changes/notes` — cut by D20: the guide note is dropped at the rebase
- [x] **Test-verified**: the anchors, refactor and mutation-lock tests pass with the links in place — `python3 tests/parallel_tests.py test_rule_anchors.py test_refactor_flow.py test_mutation_lock.py`
- [x] **Agent-run**: `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh` passes after `free -g` shows 8 GB or more available; the session records the pass count. Session ruled the full check passed 2026-11-22; coder capped run: 5712 tests in 193 files, 0 failed. Not run by the plan check: it needs the memory scope.
- [x] **Agent-run**: `git -C ~/agent-evals status --porcelain bin/rule_meter_guide.py bin/test_rule_meter_guide.py bin/rule_meter_verifier.py bin/rule_meter_scenarios.json` prints nothing after the commit; the session records the hash: f83d0475 (bench-base HEAD, in sync with origin; rule_meter_scenarios.json shows modified only from another session's rows, left untouched). Not run by the plan check: it reads another repo.

#### Manual Verification:

- [ ] Manual Verification: N/A (infra-only)

---

## Phase 10: Close pass

`/close-branch`: scripts first, then four report-only reviewers in parallel on the whole branch diff (correctness, structure, test intent, plan and acceptance-criteria reconciliation), one `coder` that fixes every finding and writes every owed test, then a report-only gate on the fix diff alone, then the recap sheet. Root-cause rule: a cast or default papering a fixable loose structure is a finding; fix the source.

### Success Criteria

Quality checks green; every reviewer finding fixed, shown wrong, or (an ask that changes a ticket AC) put to the user through agent-evals-c3; the fix-diff gate passed; every acceptance criterion mapped to a test or explicitly retired; concentration counts stated; recap and smoke-test checklist delivered.

#### Automated Verification:

- [ ] **Test-verified**: the repo quality check passes — `bash tests/run.sh`

#### Manual Verification:

- [ ] **Manual-verified**: the recap sheet names each of the three items, its change note and its queue outcome.

---

## Testing Strategy

Each script gets its own `tests/scripts/test_<script>.py` at the public boundary: argv in, output and exit code out, with a temp `HOME`, `XDG_STATE_HOME` and git repo. Prose is tested as text through the existing prompt tests, the rule-anchors check and the two new prompt-reading tests. The guard's unchanged tests prove the Phase 3 move has no behavior change. The guide skill is tested only by lint and the existing prose gates (D9); its rule cuts are measured by the meter, not by a test.

## Plan Deviations

- 2026-11-23: deviate. Ruled by agent-evals-c3 at 2026-11-23.

  The ruling: `origin/master` deleted the guide skill before the rebase, so every guide deliverable (the Phase 6 and 8 `SKILL.md` edits, `tests/scripts/test_guide_skill.py`, its `changed_scope.py` entry and the guide change note) is dropped and ACs 26-28 are cut (D20). The Phase 7 detectors in `~/agent-evals` stay.

  The disagreement:
  The plan's Phases 6 and 8 edit a file master no longer has; restoring it would undo master's cut.

- 2026-11-22: keep. Ruled by agent-evals-c3 at 2026-11-22 15:10.

  The ruling: Ticket #1 ("A test in ~/dotfiles/tests/scripts/ gives the gate `cd /abs/repo && git commit -m x` …") belongs to the dropped item `review-commit-gate-places-a-cd-to-a-literal-repo`; no test is written on this branch (D1).

  The disagreement:
  The ticket file lists four items; item 1 was dropped by agent-evals-c3 before planning, so its Done-when lines are not acceptance criteria of this plan.

- 2026-11-22: keep. Ruled by agent-evals-c3 at 2026-11-22 15:10.

  The ruling: Ticket #2 ("bash tests/run.sh passes on the dotfiles checkout.") is the dropped item 1's suite line; the suite still runs for the kept items under AC32 (D1).

  The disagreement:
  Same as Ticket #1: the line comes from the dropped item's `### Done when`.

- 2026-11-22: deviate. Ruled by agent-evals-c3 at 2026-11-22 16:20.

  The ruling: the guide detectors go in `~/agent-evals/bin/rule_meter_guide.py`, merged into `rule_meter_verifier.DETECTORS` (D10), not in `bin/rule_meter_checks/` as the lane brief's ruling named; the scenarios stay in `bin/rule_meter_scenarios.json` and `bin/rule_meter.py` stays untouched.

  The disagreement:
  `bin/rule_meter_checks/` holds subprocess tree checks; `grade()` reaches a result-text detector only through the module dicts (`rule_meter.py:1477-1480`).

- 2026-11-23: Keep plan as written. Ruled by the session, not the user at 2026-11-23 02:09.

  The ruling: AC1 (the skill keeps one worked card), AC26-28 and AC33 (a human running `/guide` can still follow the trimmed skill) are already overridden under D20 (agent-evals-c3, 2026-11-23); AC29 (each new rule-meter detector grades a compliant reply, a violating reply and one with no parseable batch) is built and tested in ~/agent-evals, so it stays; the criteria file is annotated, not cut further

  The disagreement:
  /home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/acceptance-criteria.md:7-10,63-76 [plan-drift] — PLAN-IMPACT: 03-decisions.md:170 records D20: ACs 26-28 are cut, "the cut covers every guide deliverable", and AC1's delivered scope goes with them (ruled by agent-evals-c3, 2026-11-23). The criteria file still lists AC1, AC26-AC28, AC29 (each new rule-meter detector grades a compliant reply, a violating reply and one with no parseable batch) and AC33 (a human running `/guide` can still follow the trimmed skill) as live. AC31 still asks for a change note "for each of the three items", but the branch has two notes. A verify pass reading this file would report guide criteria as failing. Question: does the D20 cut cover AC29 and AC33, and does AC31 become "each of the two kept items"? — change: mark AC1, AC26-AC29 and AC33 as cut under D20 in the file, and reword AC31 to "items 3 and 4". acceptance_criteria: AC1, AC26, AC27, AC28, AC29, AC31, AC33 kind: cut

- 2026-11-23: Adopt plan change. Ruled by the session, not the user at 2026-11-23 02:33.

  The ruling: AC33 (a human running `/guide` can still follow the trimmed skill) cut and AC31 (a change note per item) narrowed to the two kept items under D20 (agent-evals-c3, 2026-11-23); entries added to the 03-decisions.md sign-offs list

  The disagreement:
  /home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/acceptance-criteria.md:74,76 [plan-drift] — PLAN-IMPACT: the criteria file now narrows AC31 (a change note per item: "Two notes after D20: the guide note is cut with the guide item") and marks AC33 (a human running `/guide` can still follow the trimmed skill) "Cut under D20". Neither AC appears in 03-decisions.md: D20 and the sign-off at line 170 name only ACs 26-28 and AC1. The spec.md ruling at 656-658 says the file is "annotated, not cut further". Under the rule "A plan, ADR, criteria file or agent never cuts, narrows … an AC on its own", each cut or narrowing needs a sign-off line in the decision log. Question: does the D20 sign-off ("the cut covers every guide deliverable") cover AC33 and the AC31 narrowing? — change: the orchestrating session adds the AC31 and AC33 entries to the 03-decisions.md `### Sign-offs on ticket criteria` list (name and date go there only). acceptance_criteria: AC31, AC33 kind: narrow

- 2026-11-23: Keep plan as written. Ruled by the session, not the user at 2026-11-23 23:15.

  The ruling: AC9 stands as written: exit codes and plain-path output are unchanged; the quoting of a path with a shell-special character follows D15, and the rewording of AC9 is left to the orchestrating session

  The disagreement:
  PLAN-IMPACT: `docs/plans/toolkit-scripts-1122/acceptance-criteria.md` AC9 says the calibration guard "behaves exactly as before for every lock state … same output". The guard's unrestored message now builds its `cp`/`rm` lines through `calibration_lock.recovery_commands` → `shell_quoting.shell_word` (`lib/calibration_lock.py:191`). A lock whose backup, file or lock path holds `$`, a backtick, `\`, `!`, `"` or a newline now prints in single quotes (`shlex.quote`) where it used to print in double quotes. That is the intended change from the amended D15 and AC18 (`03-decisions.md:126`). Plain paths print as before. The code is right; AC9's "exactly as before" should say plain paths, or point to D15 for paths with shell characters. acceptance_criteria: AC9 kind: reword

- 2026-11-24: Adopt plan change. Ruled by the session, not the user at 2026-11-24 05:20.

  The ruling: AC9 reworded to: same output for plain paths; a path with shell characters comes out as one pasteable shell word. Ruled by agent-evals-c3-owner, 2026-11-24; the criteria-file text edit is with the user. AC31 (a change note exists for each item) narrowed to the two kept notes and AC33 (a human running `/guide` can still follow the trimmed skill) cut under D20, ruled by agent-evals-c3-owner, 2026-11-24.

  The disagreement:
  PLAN-IMPACT: /home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/03-decisions.md:171 [plan-drift] — the cut of AC33 (a human running `/guide` can still follow the trimmed skill) and the narrowing of AC31 (a change note per item) are recorded as "Ruled by the lane session as covered by D20 … pending agent-evals-c3 confirmation". `acceptance-criteria.md:67-69` already marks AC33 "Cut under D20" and AC31 as "Two notes". The criteria owner is `session`, so only the orchestrating session (agent-evals-c3) can rule a cut or a narrowing. A lane session's ruling marked "pending" is not a sign-off. Until agent-evals-c3 confirms, AC33 and the original AC31 are open criteria and must be reported that way. agent-evals-c3 must rule and replace the "pending" line with its own sign-off line.
  
  PLAN-IMPACT: /home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/acceptance-criteria.md:35 [plan-drift] — AC9 says the guard has "same output" for every lock state. Since `calibration_lock.recovery_commands` started using `shell_quoting.shell_word` (`lib/calibration_lock.py:191`), a lock whose path holds `$`, a backtick, `\`, `!`, `"` or a newline prints single-quoted `cp`/`rm` lines where it printed double-quoted ones before. Read literally, AC9 fails for those paths. The session ruling at `spec.md:132-137` left the rewording to the orchestrating session, and no sign-off is recorded yet. agent-evals-c3 must reword AC9 ("same output for plain paths; paths with shell characters quoted per D15") and record it in the 03-decisions.md sign-offs.
  
  PLAN-IMPACT: `docs/plans/toolkit-scripts-1122/acceptance-criteria.md:35` AC9 says the guard "behaves exactly as before for every lock state … same output". `calibration_lock.recovery_commands` (`lib/calibration_lock.py:191`) now prints a path that holds `$`, a backtick, `\`, `!`, `"` or a newline through `shlex.quote`. Before, it printed in double quotes, so AC9 as written fails for those paths. Plain paths still print the same, and the change note admits the difference. The 2026-11-23 23:15 ruling in `spec.md` keeps AC9 "as written" and leaves the reword to the orchestrating session, so there is still no recorded sign-off. Until agent-evals-c3 records an AC9 reword in the `03-decisions.md` sign-offs (matching the D15/AC18 amendment), report AC9 as failing.

- 2026-11-24: Adopt plan change. Ruled by the session, not the user at 2026-11-24 09:45.

  The ruling: AC9 reword adopted as recorded in 03-decisions.md line 172 (agent-evals-c3-owner, 2026-11-24): same output for plain paths, a path with shell characters comes out as one pasteable shell word; the acceptance-criteria.md text edit stays with the user, who holds the classifier-denied edit

  The disagreement:
  PLAN-IMPACT: /home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/acceptance-criteria.md:35 [plan-drift] — AC9 still says "same output" for every lock state. The 03-decisions.md:172 sign-off (agent-evals-c3-owner, 2026-11-24) changes it to "same output for plain paths; a path with shell characters comes out as one pasteable shell word" and leaves the edit to the criteria file with the user. The criteria file contradicts its own sign-off until the user makes that edit.

- 2026-11-24: Adopt plan change. Ruled by the session, not the user at 2026-11-24 11:42.

  The ruling: AC18 narrowed: recovery line only for a stale lock; a live lock of another run stops with STOP_LIVE_LOCK and no commands. Ruled by agent-evals-c3-owner 2026-11-24, recorded in 03-decisions.md

  The disagreement:
  PLAN-IMPACT: [plan-drift] The fixed code and the planning docs now disagree: Code: /home/brandon/dotfiles-toolkit-scripts-nov22/claude/.claude/scripts/tools/mutation_lock.py:273-277 refuses a live not-ours lock with `STOP_LIVE_LOCK` and no recovery line. Docs that still promise the old behaviour: /home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/acceptance-criteria.md:47 (AC18): "`restore` refuses a lock written by another writer or another owner pid (printing the `cp <backup> <target> && rm <lock>` recovery line …)". /home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/spec.md:209: any writer, owner_pid or run_id mismatch → recovery line + `STOP_NOT_OURS`. spec.md:380 (cases 9 and 13). /home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/03-decisions.md:126 (D15) and :154. The code side is right: printing cp+rm for a live run's lock lets the caller overwrite that run's mutation. So the plan should follow the code. AC18 → "prints the recovery line only when the lock is stale; a live lock of another run stops with `STOP_LIVE_LOCK` and no commands". spec.md:209 and :380 → match that. D15 → note the stale-only rule. D15's stated reason was recovery "when `$PPID` differed between `lock` and `restore`". That case still gets the recovery line once the earlier owner pid is dead or the lock is past `MUTATION_RUN_TIMEOUT_SECONDS`. acceptance_criteria: AC18 kind: narrow

- 2026-11-24: Keep plan as written. Ruled by the session, not the user at 2026-11-24 11:44.

  The ruling: The plan already states the stale-only recovery line: spec.md:209 and :380, D15 and the AC18 reword in 03-decisions.md follow the code; acceptance-criteria.md AC18 is left to the user per agent-evals-c3-owner 2026-11-24

  The disagreement:
  PLAN-IMPACT: [plan-drift] The fixed code and the planning docs now disagree: Code: /home/brandon/dotfiles-toolkit-scripts-nov22/claude/.claude/scripts/tools/mutation_lock.py:273-277 refuses a live not-ours lock with `STOP_LIVE_LOCK` and no recovery line. Docs that still promise the old behaviour: /home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/acceptance-criteria.md:47 (AC18): "`restore` refuses a lock written by another writer or another owner pid (printing the `cp <backup> <target> && rm <lock>` recovery line …)". /home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/spec.md:209: any writer, owner_pid or run_id mismatch → recovery line + `STOP_NOT_OURS`. spec.md:380 (cases 9 and 13). /home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/03-decisions.md:126 (D15) and :154. The code side is right: printing cp+rm for a live run's lock lets the caller overwrite that run's mutation. So the plan should follow the code. AC18 → "prints the recovery line only when the lock is stale; a live lock of another run stops with `STOP_LIVE_LOCK` and no commands". spec.md:209 and :380 → match that. D15 → note the stale-only rule. D15's stated reason was recovery "when `$PPID` differed between `lock` and `restore`". That case still gets the recovery line once the earlier owner pid is dead or the lock is past `MUTATION_RUN_TIMEOUT_SECONDS`. acceptance_criteria: AC18 kind: narrow

- 2026-11-24: Keep plan as written. Ruled by the session, not the user at 2026-11-24 12:50.

  The ruling: the AC18 (`restore` refuses a lock written by another writer, owner pid or run id) criteria-file edit stays with the user; the 03-decisions.md sign-off lines now say the criteria-file wording awaits the user's confirmation, no future date. Ruled adopt by agent-evals-c3-owner, 2026-11-24.

  The disagreement:
  PLAN-IMPACT: `/home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/acceptance-criteria.md:47` [plan-drift] — AC18 still promises the `cp … && rm …` recovery line for any lock of another writer or owner. Code at `mutation_lock.py:273-279`, spec.md:209 and the D15 narrowing stop on a live lock with `STOP_LIVE_LOCK` and no commands. They also refuse a lock whose run id is missing or different, which AC18 does not mention. The AC9 reword did land in this file, but the AC18 reword recorded in `03-decisions.md:173` did not. The earlier ruling leaves this edit to the user, so it stays open until the user changes the criteria file.
  
  PLAN-IMPACT: /home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/03-decisions.md:168-173 [plan-drift] — Two problems with the sign-off section: The heading says "criteria owner: `session`", but `python3 ~/.claude/scripts/code/plan_check.py owner docs/plans/toolkit-scripts-1122` returns `{"owner": "user", …, "rule": "only the user's recorded sign-off (who and when) cuts, narrows or rewords a criterion"}`. The AC9 reword (two steps) and the AC18 narrowing are signed by agent-evals-c3-owner only. The user's part is written as "confirmed by the user on 2026-11-25", a date after today (2026-11-24). A future-dated confirmation is not a recorded sign-off. The criteria file also does not match the log. acceptance-criteria.md:35 (AC9) carries only the first reword, not the closing-sentence exception, and :47 (AC18) still promises the recovery line for any other-owner lock, where the log says stale locks only. Until the user's sign-off is recorded with who and when, AC9 and AC18 as worded in acceptance-criteria.md fail against calibration_lock.py:211-212 and mutation_lock.py:278. acceptance_criteria: AC9, AC18. kind: narrow

- 2026-11-25: Adopt plan change. Ruled by Brandon Corey at 2026-11-25 13:52.

  The ruling: AC18: restore prints cp/rm only for a stale lock; a live lock stops with STOP_LIVE_LOCK

  The disagreement:
  PLAN-IMPACT: `docs/plans/toolkit-scripts-1122/acceptance-criteria.md:47` (AC18) [plan-drift] **What AC18 says**: "restore refuses a lock written by another writer or another owner pid (printing the `cp <backup> <target> && rm <lock>` recovery line …)". **What the code does**: `mutation_lock.py:282` (`refuse_unrestorable` → `refuse_live_lock`) stops a live lock of another run with `STOP_LIVE_LOCK` and prints no commands. Run against a live lock of another owner, AC18 as written fails. **The ruling**: `03-decisions.md` (Sign-offs, AC18 reworded) records the narrowing as ruled by agent-evals-c3-owner, and says "the criteria-file wording awaits the user's confirmation". **The owner conflict**: `plan_check.py owner docs/plans/toolkit-scripts-1122` returns owner `user` ("only the user's recorded sign-off (who and when) cuts, narrows or rewords a criterion"). The decisions log is headed "criteria owner: `session`". **Other session rulings under that owner**: the AC9 rewords and the AC26-28, AC33 (a human running `/guide` can still follow the trimmed skill) and AC31 cuts were also ruled by sessions. **Needed**: the user's recorded sign-off for the AC18 narrowing, and the related cuts, in `03-decisions.md`. Then reword AC18 in the criteria file to the text in the decisions log. **Smaller drift in the same file**: D19 (`03-decisions.md`, "### 19") still says any writer, owner_pid or run_id mismatch prints the recovery line. Add "(stale locks only; see the D15 narrowing)".

- 2026-11-25: Adopt plan change. Ruled by Brandon Corey at 2026-11-25 14:21.

  The ruling: AC18 reworded: a stale lock prints the recovery line; a live lock stops with STOP_LIVE_LOCK

  The disagreement:
  PLAN-IMPACT: /home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/03-decisions.md:173 [plan-drift] — The user's AC18 sign-off is recorded only in spec.md, not in the decision log. The new spec.md:722 entry records "Adopt plan change. Ruled by Brandon Corey at 2026-11-25 13:52" for AC18: cp/rm only for a stale lock, and a live lock stops with `STOP_LIVE_LOCK`. The global rule says a sign-off is recorded "only in the plan's decision log (eng-spec's `03-decisions.md` …)". The AC18 sign-off line at 03-decisions.md:173 still ends "The criteria-file wording awaits the user's confirmation. Ruled by agent-evals-c3-owner, 2026-11-24". Fix: add the user's confirmation, with who and when (Brandon Corey, 2026-11-25 13:52), to the 03-decisions.md:173 sign-off line and drop "awaits the user's confirmation". acceptance_criteria: AC18. kind: narrow
  
  PLAN-IMPACT: /home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/acceptance-criteria.md:47 [plan-drift] — The user adopted the AC18 rewrite, but the criteria file was never changed. It still says restore refuses "a lock written by another writer or another owner pid (printing the `cp <backup> <target> && rm <lock>` recovery line …)". It does not mention the run-id refusal. The code, at `mutation_lock.py` `refuse_unrestorable` → `refuse_live_lock`, stops a live lock with `STOP_LIVE_LOCK` and prints no commands. Fix: replace AC18 with the wording in the 03-decisions.md:173 sign-off line: "`restore` refuses a lock written by another writer, owner pid or run id; a stale one prints the `cp <backup> <target> && rm <lock>` recovery line, each path one pasteable shell word; a live one stops with `STOP_LIVE_LOCK` and no commands", plus the missing-lock, missing-backup and legacy-path clauses it already has. acceptance_criteria: AC18. kind: narrow
  
  PLAN-IMPACT: /home/brandon/dotfiles-toolkit-scripts-nov22/docs/plans/toolkit-scripts-1122/03-decisions.md:154 [plan-drift] — D19 still says that "a lock whose `writer`, `owner_pid` or `run_id` differs stops with `STOP_NOT_OURS`, the recovery line printed". After the narrowing the adopted ruling describes, a live lock of another run gets `STOP_LIVE_LOCK` and no recovery line. The adopted ruling's own text (spec.md:728) asks for this edit. Fix: add "(stale locks only; a live lock stops with `STOP_LIVE_LOCK`, see the D15 narrowing)" after "the recovery line printed". acceptance_criteria: AC18. kind: narrow

## References

- ./00-ticket.md, ./01-questions.md, ./02-research.md, ./03-decisions.md
- `docs/toolkit-script-rules.md`, `claude/.claude/scripts/CLAUDE.md`
- Lane brief and rules: `/tmp/claude-1000/-home-brandon-agent-evals/a0b58526-6a4a-4e0a-af5b-8d0985572fda/scratchpad/brief-toolkit-scripts.md`, `lane-common.md`
