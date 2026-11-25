---
date: 2026-11-22
git_commit: 9a1bef2c58d3ddb713cc4cf7caf581dfeed95794
branch: fix/toolkit-scripts-nov22
topic: Git gates (commit review and git discipline), guide and refactor skill text, mutation-tester lock procedure, script and test conventions, rule-meter
tags: [gates, git-calls, reviewed-tree, guide-skill, refactor-flow, mutation-tester, opencode-ports, tests, rule-meter]
status: complete
---

# Research: git gates, skill and agent prose, lock/backup scripts, test conventions, rule-meter

## Findings

### Q1. `gates/review-commit-gate`

- No file named `review-commit-gate` exists under `claude/.claude/scripts/gates/`. The commit-time gate was `claude/.claude/scripts/review/review_commit_gate.py`, deleted together with `tests/scripts/test_review_commit_gate.py` in commit `4732aaf3` ("Replace review-commit-gate with a push-time reviewed-tree check") (`git log --diff-filter=D`).
- Remaining mentions of it in the tree are in `docs/plans/*/plan.md` files and one fixture line (`tests/scripts/fixtures/script_path_quoted_heredoc.sh:15`). Neither `settings.json` nor any script references it.
- The replacement is rule 8 of `claude/.claude/scripts/gates/git_discipline_gate.py`, documented at lines 32-34: git push, and `gh pr create` in the hook's cwd, are denied when the repo's HEAD tree (notes paths left out) differs from every tree a converged review recorded for that repo; a repo with no record passes.
- Flow, stdin to output:
  - `main` (`git_discipline_gate.py:497-510`) returns 0 when `CLAUDE_SKIP_HOOKS` is set, reads stdin, calls `run(raw)`; a `DenyError` becomes `hook_input.emit_decision("deny", ...)`; any other exception becomes a fail-closed deny "internal error (exit 1)"; the file ends with `hook_input.run_gate(main)`.
  - `run` (`:377-417`) parses the payload (parse failure raises a fail-closed `DenyError`), takes `payload_cwd` from `cwd` (default `"."`), and calls `git_calls(command, payload_cwd)`.
  - `check_push_reviewed(command, calls, payload_cwd)` (`:451-460`) collects `call.directory` for every call whose `subcommand == "push"`, appends `payload_cwd` when `opens_pull_request(command)` (`:442`, a step whose words are `gh pr create`), and for each directory calls `reviewed_tree.push_review_state(directory)`; `PUSH_CHANGED` raises `DenyError(PUSH_UNREVIEWED_DENIED)`.
  - `push_review_state(repo_dir)` (`lib/reviewed_tree.py:324-352`): `script_utils.repo_root(repo_dir)` gives `top`, no work tree -> `PUSH_NO_RECORD`; reads `shared_bases_file()` entries for `str(top)`; none -> `PUSH_NO_RECORD`; reads `notes_paths.committed_notes_list(top)`; for each entry newest first, `tree_fingerprint(top, base=entry["base"], target="HEAD", notes_entries=...)`, equal to `entry["tree"]` -> `PUSH_REVIEWED`; a `TreeFingerprintError` skips the entry; no match -> `PUSH_CHANGED`. Constants at `reviewed_tree.py:52-54`.
  - The repo folder comes from `GitCall.directory`, computed by `lib/git_calls.py` (see Q2). The deny text is the test's `PUSH_DENIED` string at `tests/scripts/test_git_discipline_gate.py:949`.
- Records are written by `reviewed_tree.record_shared_base` (`:314`) and `record_base` (`:293`); readers `is_reviewed` (`:386`), `shared_record_covers` (`:410`).

### Q2. `gates/git-discipline-gate`: `-C` and `cd`

- The file is `claude/.claude/scripts/gates/git_discipline_gate.py` (514 lines). Imports at `:42-58`: `import_guard`, `directory_emptying_deletes`, `docker_run_names`, `hook_input`, `reviewed_tree`, `script_utils`, `shell_command`, `shell_statements`, `user_prompts`, and from `git_calls` `REPO_ENVIRONMENT_NAMES`, `git_calls`, `is_linked_worktree`. It imports none of `git_commit_calls.py`, `shell_directory.py` or `git_alias_commits.py` directly.
- The docstring (`:1-39`) says: "Rules 4 and 5 read the branch of the repo each call runs in. How the gate finds git calls and the directory each runs in is documented in git_calls.py."
- `-C`, `cd` and directory placement are resolved in `lib/git_calls.py`: `git_calls(command, directory, context)` (`:396`) returns `GitCall` tuples (`:86`); `git_call(words, directory, context, resolved_words)` (`:179`) reads options via `option_path` (`:120`) and `joined_directory` (`:129`); `cd_directory(words, directory)` (`:447`) handles `cd`; `call_is_placed` (`:169`) decides whether the directory is known; `has_unfollowed_directory_move` (`:260`), `has_hidden_directory_move` (`:275`) and `has_conditional_cd` (`:290`) flag moves it cannot follow; `is_linked_worktree` (`:243`) and `is_linked_git_folder` (`:222`) classify a folder.
- Option parsing is in `lib/shell_command.py`: `git_options(words)` (`:550`), `command_after_wrappers` (`:632`), `step_words` (`:714`), `segment_words` (`:724`), `git_c_directory(words, directory)` (`:958`).
- `lib/shell_directory.py` (85 lines) holds `path_word` (`:10`), `path_word_is_absolute` (`:21`), `cd_folder` (`:33`), `ShellDirectory` (`:48`).
- Inside the gate, `literal_dir_targets(step)` (`:180-194`) reads the literal repo-selecting text of the git call opening a step: wrapper words starting with `REPO_ENV_PREFIXES`, and each `-C`, `--git-dir`, `--work-tree` option from `shell_command.git_options` (`option + "=" + value`).
- Other `run` checks (`:377-417`): `check_coder_index`, stash, `check_autostash`, amend (with `user_approved_amend`), attribution regex, `check_destructive` and `check_branch` per call, then `check_push_reviewed`, `check_directory_emptying`, `check_docker_run_names`.
- `lib/git_commit_calls.py` (275 lines) has `git_call_commits` (`:148`) and `git_commit_dirs` (`:249`); `lib/git_alias_commits.py` is the alias reader. The gate imports neither (see Dormant scaffolding).

### Q3. Tests for the two gates

- No test file for the commit-time review gate remains (`test_review_commit_gate.py` deleted in `4732aaf3`).
- `tests/scripts/test_git_discipline_gate.py` (1105 lines):
  - Path: `SCRIPT = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or toolkit_paths.GATES_DIR) / "git_discipline_gate.py"` (`:13-14`); `import toolkit_paths` at `:12`.
  - `GateCaseBase(unittest.TestCase)` (`:21`): `setUp` makes a temp dir with cleanup; `repo_on(branch, claude_md=None)` runs `git init -q` plus `symbolic-ref HEAD`; `run_raw(stdin, cwd, env_extra)` runs the script as a subprocess with env `PATH`, `HOME=tmp`, `TMPDIR=tmp`; `run_command(command, cwd, branch, transcript_path, agent_type)` builds `{"tool_input": {"command": ...}}` JSON; `write_transcript(*records)`; `typed_prompt(text)` builds a user record (`origin.kind` human, `promptSource` typed); `reason_of(finished)`.
  - Classes: `GitDisciplineGateTest` (`:78`), `DestructiveGitCallsTest` (`:598`), `NamesProtectedBranchTest` (`:930`), `PushReviewedTreeTest` (`:952`), `DirectoryEmptyingGateTest` (`:1020`), `UnnamedDockerRunGateTest` (`:1079`).
  - `PushReviewedTreeTest` covers rule 8: setUp patches `HOME` to the temp dir, makes a repo with `app.py` committed, and loads `reviewed_tree` through `load_reviewed_tree()` (`:943`, inserts `toolkit_paths.LIB_DIR` into `sys.path`). Tests: passes when HEAD holds the reviewed tree (`:986`), after a review of a committed branch (`:992`), denied when code changed after review (`:998`), passes when only notes changed (`:1007`), passes with no review record (`:1013`).
- `tests/scripts/test_git_calls.py` has `HasConditionalCdTest` (`:12`), `CommentEndingInBackslashTest` (`:41`), `HashAfterEscapedBlankTest` (`:52`).
- `tests/scripts/toolkit_paths.py`: `TREE_CLAUDE_DIR` (`:11`), `CLAUDE_DIR` (`:12`, env `TOOLKIT_CLAUDE_DIR`), `REPO_ROOT` (`:13`), `SCRIPTS_DIR` (`:16`), `CODE_DIR`, `REVIEW_DIR`, `TELEMETRY_DIR`, `LIB_DIR`, `TOOLS_DIR`, `GATES_DIR` (`:17-22`), `FIX_DIFF_SCRIPT` (`:23`), `CODE_SKILL_FILE` (`:25`), `CODE_FORK_AGENT_FILE` (`:26`), `WORK_HOOKS` (`:30`), `CODER_GATE_LIB_MODULES` (`:33`), `first_python_that_starts(names)` (`:42`); importing it guards the real ledger (docstring `:4`). Its own test: `tests/scripts/test_toolkit_paths.py`.

### Q4. `skills/guide/SKILL.md`

- 236 lines. Frontmatter `name: guide`, description at `:2-3`. Sections: intro `# guide` (`:6`, write ~40 JSON lines per card, never HTML; use past ~5 judgment calls); `## The commands` (`:16`); `## The batch` (`:35`); `## A card` (`:66`); `## Blocks — what they read` (`:79`); `## Fields — what they do` (`:100`); `## Three worked cards` (`:114`); `## Rules` (`:200`); `## Reading the answers` (`:217`).
- Commands listed (`:18-27`): `guide --format-version`, `guide push ./questions.json`, `guide push -`, `guide wait <id>`, `guide wait <id> --timeout 1800`, `guide list`, `guide read <id>`. `push` fills `source.cwd`, `source.repo`, `source.branch`; `--label` names the inbox rail entry.
- Batch keys (`:37-62`): `guide_version` ("0.1.0", first key), `title`, `subtitle`, `instructions`, `defaults.response`, `summary` (`progress`, `counters[]` with `label/field/equals`, `rates[]` with `label/field/numerator/denominator`), `cards[]`; `id` omitted at batch level.
- Card keys (`:66-77`): `id`, `title`, `tags`, `blocks`, `response`, `meta`.
- Block types (`:83-93`): `text` (`text`, `format` plain|pre|markdown), `callout` (`text`, `footnote`, `tone`), `code` (`code`, `language`), `table` (`columns[]`, `rows[]`, `note`, `truncated`), `keyvalue` (`pairs[]`), `diff` (`diff`), `json` (`value`), `image` (`src` data URI only, `alt`, `caption`), `columns` (`columns[]` of `{label, blocks[]}`). Every block takes optional `label` and `collapsed`. `tone`: info, warn, bad, good, mute.
- Field types (`:102-109`): `choice` (`options[]`, `key`), `text` (`multiline`, `placeholder`, `max_length`), `rating` (`min`, `max`, `labels`), `compare` (`options[]`), `multichoice` (`options[]`), `boolean` (`true_label`, `false_label`). Option shape `{value, label, tone?, key?}`; a card is answered when every `required: true` field has a value.
- Answers shape (`:217-236`): `complete`, `degraded`, `degraded_cards`, `stats{total, answered}`, `answers[]` of `{card_id, title, meta, values}`.
- The skill text says only that `guide --format-version` prints "the format this build speaks". No `--format-version` output block is recorded in the skill or anywhere else searched. `guide` is not installed on this machine (`command not found`) and no source for it exists in this repo or `~/agent-evals`. The skill mentions "GUIde" (`:236` region).
- `claude/.claude/settings.json:195` has `"guide": "user-invocable-only"`.
- Queue item `~/agent-evals/queue/guide-skill-point-to-the-guide-binary-instead-of.md` exists.

### Q5. refactor skill `log` input and `refactor_flow.py`

- `claude/.claude/skills/refactor/SKILL.md` (133 lines): sections `# Refactor` (`:7`), `## Never modify a test to make a refactor pass` (`:14`), `## Modifiers` (`:18`), `## Script` (`:22`), `## Instructions` (`:26`), `## Code to refactor` (`:131`). `:24` gives the call form `python3 ~/.claude/skills/refactor/scripts/refactor_flow.py <verb>` and says each verb ends with `NEXT:` or `STOP:`.
- Step 5 `Log and hand off` (`:64`): write the JSON file at the path the prep script's `NEXT:` line named, run `refactor_flow.py log --mode <branch|targeted|simplify> --input <file> [--base REF]`; one input file per invocation; re-running skips rows already written. Keys (`:65-68`): `finder`, `lane` (required with a finder), `result`; `findings[]` of `{class, disposition, actioned, file, line, desc}` plus `escape`, `severity`, `miss_reason` for escapes; `guards` as `{"<class>": "<guard>"}`; `handoff` with `files[{path, change}]`, `tests_run`, `flagged`, `plan_impact`; `modifier`. A fenced `json` example follows (`:70-100`).
- Audit and simplify steps call `log --mode audit` (`:115`) and `log --mode simplify` (`:127`, `:129`).
- `claude/.claude/skills/refactor/scripts/refactor_flow.py` (1097 lines):
  - Docstring (`:2-39`) lists the five verb forms, the input-file JSON shape, and "Exit codes: 0 ok or a clean stop, 1 bad input (nothing was written), 2 a writer refused a row."
  - Parser: `parse_arguments` (`:1063`), `argparse.ArgumentParser(prog="refactor-flow")` with required subparsers `branch-prep` (`--head`, `--base`, `--jscpd-timeout`), `audit-prep` (`target`, `--jscpd-timeout`), `simplify-prep` (`target` nargs +, `--slice`), `log` (`--mode` required, choices branch, targeted, audit, simplify; `--input` required; `--base`), `handoff` (`--input` required). No custom `--help` text, `description` or per-argument `help=` is set: `--help` is argparse's generated output.
  - `main` (`:1085-1094`) dispatches through a handler dict; `RefactorFlowError` prints `refactor-flow: <message>` to stderr and returns 1. `RefactorFlowError` is at `:117`.
  - Input reading: `read_refactor_log(path)` (`:806`) raises `cannot read --input <path>: <err>` and `--input <path> must hold a JSON object`.
  - Validation: `require_text` (`:599`), `single_line` (`:606`), `one_line_path` (`:616`, with `SWALLOWED_PAIR` regex at `:613`), `validate_finding` (`:625`), `validate_escape_finding` (`:659`), `validate_handoff` (`:673`), `require_escape_guards` (`:693`), `validated_targets` (`:700`), `validate_log(mode, refactor_log)` (`:709-745`: finder must be omitted in targeted mode and one of `FINDERS` otherwise; `lane` required with a finder; `findings` must be a list; `guards` an object; `result` a string; audit mode refuses `handoff`). Messages are f-strings such as ``f"{where}: `{key}` must be a non-empty string"``.
  - `log_verb` (`:1006`), `handoff_verb` (`:1048`), `check_targets_match` (`:969`), `log_next` (`:986`), `pending_rows` (`:995`), `check_writer_rows` (`:949`). Idempotence state: `written_state_file` (`:870`), `row_hash` (`:874`), `load_written_state` (`:883`), `locked_state_file` (`:898`), `record_written` (`:911`), `write_rows` (`:937`).
  - `next_line(text)` (`:283`) formats the `NEXT:` line; `NO_HISTORY_STOP` (`:114`) is the stop line.
- Tests: `tests/scripts/test_refactor_flow.py` (1953 lines, one class `RefactorFlowTest` at `:48`). Examples: `test_the_log_input_example_in_the_skill_logs_on_the_first_call` (`:342-352`) extracts the first fenced `json` block from `SKILL.md` with `re.search(r"```json\n(.*?)```", ..., re.S)` and feeds it to `log branch`; `test_bad_input_exits_1_and_writes_nothing` (`:479`); `test_log_refuses_a_plan_structure_finding_logged_as_a_fix` (`:194`); `...escape_finding_with_a_missing_or_unlisted_miss_reason` (`:212`); `...writes_nothing_when_the_run_writer_refuses_a_row` (`:242`); `test_log_missing_guard_writes_nothing` (`:1562`); file-path tests `:1590`, `:1602`, `:1636`, `:1658`; `test_log_reports_a_writer_refusal_and_a_rerun_writes_only_the_missing_rows` (`:1667`); `test_log_audit_refusal_does_not_point_at_review` (`:1707`); `test_log_simplify_escape_error_names_the_finding` (`:1772`); `test_log_rejects_a_newline_in_a_handoff_scalar` (`:1803`). No test file name contains a `--help` check; `rg` for `--help` in this test file was not part of the read set.
- `tests/parallel_tests.py:42` lists it in `HEAVY_FIRST`; `tests/changed_scope.py:32` lists it in `PROMPT_READING_TESTS`.
- Queue item `~/agent-evals/queue/refactor-skill-have-refactor-flow-py-print-the-log.md` exists.

### Q6. `agents/mutation-tester.md`

- 152 lines. Frontmatter `:1-7` (`model: sonnet`, tools `Bash, Read, Write, Edit, Glob, Grep, LSP`).
- Dispatch contents (`:13-21`): target file and exact mutation, expected killing test(s), test command; anything missing -> stop.
- Step 0 (`:23-42`), preconditions ("all five" in the heading; the list holds four bullets plus the baseline run): run `git rev-parse --show-toplevel && git status --porcelain`; no test command -> stop; not a git repo -> stop; lock file exists -> STOP; target not in the working tree or not the file named -> stop. Lock path `${XDG_STATE_HOME:-$HOME/.local/state}/claude-calibration/lock.json` or the old `~/.claude/calibration-lock.json` (`:31`). Liveness check `python3 ~/.claude/scripts/gates/calibration_guard.py --live --session-pid "$PPID"`: exit 0 means live, report owner and worktree, stop (`:31-36`). Baseline suite run first; not green -> `INDETERMINATE — baseline not green`; capture executed-test count (`:39-42`).
- Step 1 (`:44-61`): `mkdir -p .../claude-calibration/backups`; `cp <target> .../backups/$(basename <target>).bak`; `sha256sum <target> | cut -c1-16` for the pre-mutation content hash; `jq -n ... > .../claude-calibration/lock.json` with fields `ts`, `kind: "mutation-test"`, `writer: "mutation-tester"`, `file`, `backup_path`, `pre_hash`, `class`, `line`, `worktree`, `owner_pid` (from `$PPID`).
- Step 2 (`:63-69`): one Edit with exactly the given mutation; never `sed -i`; on a non-applying mutation restore per Step 4 and report `INDETERMINATE — mutation does not apply`.
- Step 3 (`:71-92`): verdicts KILLED, INDETERMINATE (expected test did not run), EQUIVALENT, SURVIVED.
- Step 4 (`:94-117`): restore on every path with `cp <backup_path> <target>` (never `git checkout`, `Write`, or `Edit`); verify `sha256sum <target> | cut -c1-16` equals `pre_hash`; match -> `rm .../lock.json` and report hash-verified restore (if a safety gate blocks the removal, report and print the command for the caller); mismatch -> stop loudly, keep the lock.
- `## Hard limits` (`:119`) and `## Output Format` follow.
- The lock is read by `claude/.claude/scripts/gates/calibration_guard.py` (registered as a SessionStart hook at `settings.json:522`, `sh ~/.claude/scripts/tools/hook-python ~/.claude/scripts/gates/calibration_guard.py`). The steps exist only as prose; no script performs them. Queue item `~/agent-evals/queue/mutation-tester-move-the-lock-backup-and-restore.md` exists.

### Q7. Existing lock, backup and restore scripts

- `claude/.claude/scripts/lib/file_lock.py` (34 lines): `LockTimeoutError(OSError)` (`:12`), `hold_exclusive(lock_path, timeout_seconds)` context manager (`:16-34`) using `fcntl.flock(LOCK_EX | LOCK_NB)` with a retry of `RETRY_SECONDS = 0.02` (`:9`). No CLI, no `--help`. Production caller: `review/handback_store.py:18,635`. Tests: `tests/scripts/test_file_lock.py` (`HoldExclusiveTest`, `:15`).
- `claude/.claude/scripts/lib/file_backup.py` (84 lines): `MAX_FILE_BYTES = 50 MiB` (`:9`), `Backup(root, backup_dir, saved, unsaved)` (`:12`), `save_files(root, paths, backup_dir, max_file_bytes)` (`:23`), `restore_missing(backup)` (`:50`), `restore_changed(backup)` (`:66`), `discard(backup)` (`:82`). No CLI. Callers: `review/review_loop_untracked.py:9,57,58,75,91`, `review/review_loop_ruled_out.py:8,86,108-110,134,142`. Tests: `tests/scripts/test_file_backup.py` (`FileBackupTest`, `:13`).
- `claude/.claude/scripts/lib/script_utils.py`: `repo_root` (`:594`), `read_ledger` (`:748`), `write_text_atomically(path, content)` (`:1357`), `state_file_path(state_dir, name, suffix)` (`:1397`), `read_jsonl` (`:1441`). The `scripts/CLAUDE.md` owner list names `lib/file_lock.py` for cross-process locks (line 25) and `script_utils` for state file paths and atomic writes.
- A second flock use: `code/coder_gate.py:342` and `:855` call `fcntl.flock(lock_file, fcntl.LOCK_EX)` directly.
- `gates/calibration_guard.py` (167 lines) is the only script that reads the calibration `lock.json`: module doc `:4-13`, `lock_field` (`:30`), `parse_stamp` (`:54`), `session_pid_argument` (`:62`), `lock_is_live` (`:72`), `live_notice` (`:88`), `main` (`:100`; `--live` printed nothing and exit 0 only when the lock is live, else 1; `--session-pid <pid>` calls a calibrate-writer lock stale). It takes arguments by hand from `sys.argv`, not argparse. `MUTATION_RUN_TIMEOUT_SECONDS = 60 * 60` (`:27`). Tests: `tests/scripts/test_calibration_guard.py` (`CalibrationGuardTest :47`, `LiveLockTest :170`, `SameSessionLockTest :204`) and `test_calibration_refs_guard.py`.
- No script under `claude/.claude/scripts/` writes the calibration `lock.json` or its `backups/` folder.

### Q8. opencode ports

- `opencode/.config/opencode/agents/` holds `mutation-tester.md`, `smell-reviewer.md`, `complexity-reviewer.md`, `test-intent-reviewer.md`, `test-reviewer.md` (among others).
- `opencode/.config/opencode/skills/` holds only `merge`, `open-pr`, `rebase`. There is no `guide` or `refactor` skill copy; `commands/refactor.md` (4 lines) reads "Load the `refactor` skill and follow its instructions. $ARGUMENTS", description "Smart refactorer — dispatches coder subagent(s), then auto-runs review". No `claude/.claude/commands/refactor.md` exists.
- `opencode/.config/opencode/agents/mutation-tester.md` differs from the claude original (diff):
  - Frontmatter: `model: opencode-go/mimo-v2.6-pro`, `mode: subagent`, `color: "#ef4444"` in place of `model: sonnet`, `tools: ...`, `color: red`.
  - Opening: an authority paragraph in place of "Hand back a tree byte-identical to the tree you were handed."
  - Step 0 heading "all four"; the "test command not stated -> stop" bullet is absent (claude has it at `:29`); the lock bullet names `~/.claude/calibration-lock.json` only, mentions `/calibrate`, says "The lock is GLOBAL, not per-repo", and has no `calibration_guard.py --live` check.
  - Step 1: backup at `~/.claude/calibration/$(basename <target>).bak` and `mkdir -p ~/.claude/calibration`; lock written to `~/.claude/calibration-lock.json` with fields `ts, kind, file, backup_path, pre_hash, class, line` (no `writer`, `worktree`, `owner_pid`).
  - Step 4: `rm ~/.claude/calibration-lock.json`.
  - Extra rationale sentences throughout (e.g. "Do not soften the distinctions", "Findings route to `/fix` through your dispatcher"); "Never `sed -i`; a hook blocks it" absent in Step 2.
- Per `CLAUDE.md` the ports keep adaptations (CLAUDE.md -> AGENTS.md, opencode frontmatter); `docs/rule-anchors.md` lines 129-137 list the claude agent's sections by anchor.

### Q9. Other references; how tests check prose

- guide: `settings.json:195` only (`"guide": "user-invocable-only"`); other `guide` hits in `tests/` are unrelated filenames (`docs/guide.md` fixtures).
- refactor skill log template: `skills/close-branch/SKILL.md:17` (`branch-prep`) and `:68` ("in the input shape of `~/.claude/skills/refactor/SKILL.md` Step 5"); `skills/_shared/handoff-block.md:32`; `docs/rule-anchors.md:126-127`; `ruff.toml:28` (E402 exception for `refactor_flow.py`); `skills/refactor/scripts/clone_pairs.py:4`; `tests/scripts/test_comment_bloat_gate.py:382` (fixture name only).
- mutation-tester procedure: `skills/test-audit/SKILL.md:19,21` (dispatch `mutation-tester`, verdicts "defined in mutation-tester.md"); `agents/test-intent-reviewer.md:55,92` and its opencode port `:72,120`; `gates/calibration_guard.py:4,77,141,158`; `tests/scripts/test_calibration_guard.py:82,88,217-218`; `docs/rule-anchors.md:129-137`.
- Prose tests: `tests/changed_scope.py:19-25` defines `PROMPT_MARKDOWN` (`^claude/\.claude/(skills|agents)/.+\.md$`) and the tuple `PROMPT_READING_TESTS` (the test files that open a skill or agent file of the real tree; "A new test that reads a prompt file of the real tree goes in this list"); `tests/scripts/test_prompt_reader_list.py` keeps that list honest by checking it against the files tests read; other tests that read prose: `test_review_loop_prompt_file.py`, `test_code_skill_text.py`, `test_guidance_rules.py`, `test_dead_prose_gate.py`, `test_spec_agent_tools.py`, `test_agent_hook_registration.py`, `test_agent_model_guard.py`, `test_stale_prose.py`, `test_rule_anchors` (named in the `changed_scope.py` comment as added by hand). `test_refactor_flow.py:342-352` parses the skill's JSON example; `:1276` reads `close-branch/SKILL.md`.

### Q10. Test suite and script conventions

- `tests/run.sh` (61 lines): `set -euo pipefail`, unsets `CLAUDE_SKIP_HOOKS`; (1) `tests/lint.sh`, exit 2 (ruff missing) stops the run with exit 1; (2) `python3 tests/duplicate_code.py`; (3) `tests/review_gate_unchanged.py snapshot` of the real review-gate keys; (4) `tests/changed_scope.py scope` -- `markdown-only` runs only `changed_scope.py kept` files, else the full set; (5) `python3 tests/parallel_tests.py [files]` with `TMPDIR` set to a run temp folder and `SUITE_SLOT_DIR` from `parallel_tests.slot_folder()`; (6) `review_gate_unchanged.py compare`; last line `FAILED: <steps>` among `lint`, `duplicate-check`, `tests`, `review-gate-state`, exit 1. `REAL_PLANS=1` also parses real plans under `~/dev`.
- `tests/lint.sh` (76 lines): exit 0 clean, 1 failure, 2 no ruff. With no arguments: `ruff check --no-cache claude/.claude/scripts claude/.claude/skills tests/scripts tests/duplicate_code.py`, a C901 report (not a failure), and a C901 gate over `codeFlowFiles` and `reviewFlowFiles` (arrays at `:21-36`, including `lib/git_alias_commits.py` and `lib/git_commit_calls.py`). With file arguments: only `.py` files (plus `review/verify-log` and `review/verify-prep`), ruff on each, C901 on the gated ones.
- `tests/parallel_tests.py` (291 lines): runs each `tests/scripts/test_*.py` as its own process, `nproc` at a time, slowest first (`HEAVY_FIRST :42`, `SHARDS = {"test_review_loop_script.py": 4}` `:38`); with names runs only those files; `FILE_TIMEOUT_SECONDS` 1200 (env `TEST_FILE_TIMEOUT_SECONDS`); `WORKER_NICENESS = 10`; `--worker FILE I N` internal; `REPO_ROOT` env override; a file fails if its shard counts do not add up.
- `docs/toolkit-script-rules.md` (scripts under `claude/.claude/scripts/` and `skills/*/scripts/`): snake_case Python names; `bash tests/lint.sh <files>` before hand-over; read real inputs and list every shape before writing a grammar; one function per format with loud failure and a `check` command; search callers before changing output, exit code or arguments; capture one real event per hook type as a fixture; ledger is optional (`script_utils.read_ledger`, `telemetry/ledger-write`); no verb, route or state field added to a script over 1000 lines; helper search in `lib/` first; tests at `tests/scripts/test_<script>.py` reading the script path from one env var; run changed tests with `python3 tests/parallel_tests.py <file>`; `bash ~/dotfiles/tests/run.sh` before done.
- `claude/.claude/scripts/CLAUDE.md`: one owner per fact (Search first, Owners list), steps pass JSON, a new status is a named constant in its owner, no swallowed exception in a hook, each gate states fail-open or fail-closed in a comment, state written atomically via `write_text_atomically`, tests under `tests/scripts/` with `toolkit_paths.py`.
- `refactor_flow.py` is 1097 lines, which is over the 1000-line mark in the size rule. `git_discipline_gate.py` is 514 lines.

### Q11. rule-meter (`~/agent-evals/bin/`)

- Files: `rule_meter.py` (2723 lines), `rule_meter_scenarios.json` (1747 lines, 105 scenarios keyed `A`..`PV01`), `rule_meter_shipped.json`, `rule_meter_coder5.py` (206), `rule_meter_config.py` (102), `rule_meter_families.py` (104), `rule_meter_fixture.py` (224), `rule_meter_index.py` (82), `rule_meter_plans.py` (29), `rule_meter_regress.py` (182), `rule_meter_stacks.py` (362), `rule_meter_verifier.py` (76); folders `rule_meter_checks/` and `rule_meter_plants/`.
- `rule_meter.py` docstring (`:2-37`): one cell is rule x prompt level (supportive, neutral, competing) x arm (on, off); a cell builds a bench tree from the ticketsim fixture, appends the global CLAUDE.md (arm off: minus the rule text), runs `claude -p` on the rule's task, and grades tool calls and the tree. Outcomes COMPLIED, VIOLATED, NO_TEST, NO_CHANGE, ERROR. Runs live under `~/dev/evals/rulemeter1/`.
- CLI (`main :2671`, argparse subcommands `:2673-2695`): `run --rule --level --arm [--run N] [--dry-run]`; `run-all [--runs N] [--level] [--rule] [--dry-run]`; `summary`; `regress [--rule slug] [--file] [--runs] [--dry-run]`.
- Scenario fields seen across the JSON: `name`, `rule_text`, `rule_file`, `rule_source`, `agent`, `toolkit_root`, `model`, `plant`, `setup`, `detector`, `task`, `suffix` (per level: supportive, neutral, competing), `family`, `split`, `note`, `retired`. Example scenario `A` (`rule_meter_scenarios.json`): `name: no-unstage`, `setup: stage_readme`, `detector: no_unstage`.
- Detectors: `SCENARIOS = HERE / "rule_meter_scenarios.json"` (`rule_meter.py:83`); `load_scenarios` (`:1578`); `grade(scenario, tool_calls, tree, base_sha, result_text)` (`:1435`) reads `scenario["detector"]`; `grade_coder5` (`:1365`) and `grade_stacks` (`:1423`) delegate to the coder5 and stacks modules. In `rule_meter.py` detector functions are named `detect_<detector>` (e.g. `detect_no_unstage :291`, `detect_keeps_untracked_file :301`, `detect_script_outside_tree :329`, `detect_no_unasked_worktree :355`, `detect_asks_done_by_session :369`, `detect_changed_tests_only :556`, `detect_no_nested_call_args :599`, `detect_max_nesting :624`, `detect_ternary_arg :688`, `detect_max_params :707`, `detect_no_blockquote :845`, `detect_extend_not_copy :856`, `detect_red_test_kept :908`). Plants applied at `:2411-2412` (`PLANTS[scenario["plant"]](tree)`); `run_cell` at `:2488`.
- 82 distinct `detector` values appear in the scenarios JSON.
- Checks: `rule_meter_checks/` holds `async_panel_states.mts`, `async_view_states.mts`, `branch_has_failing_test.py`, `incidental_owner_filters.py`, `keep_behavior.mts`, `keep_date.mts`, `keep_quantity.mts`, `second_owner_mutation.py`, `stale_docs.mts`, `sweep_defaults.mts`, `sweep_owner_check.mts`, `weak_fix_test.mts`. `branch_has_failing_test.py` is run as `python3 -I -B branch_has_failing_test.py <app dir> <added lines JSON>`, prints one JSON line (`loaded`, `baseline`, `branches`, `survivors`, `survivor_sites`) and imports `python_mutation` from the parent folder. `rule_meter_plants/` holds scenery trees (`async_panel`, `async_view`, `catalog_app`, `fixture_filter_ts_base`, `fixture_filter_ts_head`, `fixture_order_ts_base`, `fixture_order_ts_head`, `keep_behavior`, `keep_date`, `keep_quantity`, ...).
- `rule_meter_config.py:1-25`: a per-run config folder holding only a copy of `.credentials.json` (`LOGIN_FILE_NAME`), `FOLDER_PREFIX = "rule-meter-config-"`, `MIN_REMAINING_MS`, `WAIT_POLL_SECONDS = 30`, `WAIT_LIMIT_SECONDS = 45 * 60`, `LoginError`.
- Tests (in `bin/`): `test_rule_meter.py` (308 test methods; classes such as `StreamParsingTest :24`, `NoUnstageTest :55`, `AsksDoneBySessionTest :105`), `test_rule_meter_branches.py` (53), `test_rule_meter_config.py` (21), `test_rule_meter_families.py` (14), `test_rule_meter_fixture.py` (20), `test_rule_meter_regress.py` (23), `test_rule_meter_stacks.py` (15), `test_rule_meter_verifier.py` (5).

## Dormant scaffolding

- `lib/git_commit_calls.py:249` `git_commit_dirs` and `lib/git_alias_commits.py` have no production importers in `claude/.claude/scripts/` after the commit-time gate was deleted; both remain listed in `tests/lint.sh:21-27` (`reviewFlowFiles`) and in `scripts/CLAUDE.md` owners (`git_call_commits`, `git_commit_dirs`, `git_alias_commits.py`). `git_call_commits` (`:148`) is not imported by `git_discipline_gate.py`.
- `reviewed_tree.is_reviewed` (`:386`), `record_reviewed` (`:364`), `shared_record_covers` (`:410`), `last_commit_fingerprint` (`:429`), `matches_recorded_base` (`:449`) are not called by `git_discipline_gate.py`; the gate calls only `push_review_state` (`:324`).
- `docs/plans/*/plan.md` files still name `review_commit_gate.py` and `review-commit-gate`, which no longer exist.
- `calibration_guard.py --live --session-pid` is used by `mutation-tester.md:31-32` (claude copy) but not by the opencode copy; the opencode copy writes the legacy `~/.claude/calibration-lock.json` path, which `mutation-tester.md:31` (claude) lists as "the old" path.
- `skills/guide/SKILL.md` has no recorded `--format-version` output and the `guide` binary source is not in the searched trees.
- `tests/scripts/test_refactor_flow.py` has no `--help` test found by test name.

## Code References

- `claude/.claude/scripts/gates/git_discipline_gate.py:377` — `run`, the gate flow.
- `claude/.claude/scripts/gates/git_discipline_gate.py:180` — `literal_dir_targets`, `-C`/`--git-dir`/`--work-tree` text.
- `claude/.claude/scripts/gates/git_discipline_gate.py:442` — `opens_pull_request`.
- `claude/.claude/scripts/gates/git_discipline_gate.py:451` — `check_push_reviewed` (rule 8).
- `claude/.claude/scripts/gates/git_discipline_gate.py:497` — `main`, fail-closed wrapper.
- `claude/.claude/scripts/lib/reviewed_tree.py:324` — `push_review_state`.
- `claude/.claude/scripts/lib/git_calls.py:396` — `git_calls`; `:179` `git_call`; `:447` `cd_directory`; `:129` `joined_directory`; `:243` `is_linked_worktree`.
- `claude/.claude/scripts/lib/shell_command.py:550` — `git_options`; `:632` `command_after_wrappers`; `:958` `git_c_directory`.
- `claude/.claude/scripts/lib/shell_directory.py:33` — `cd_folder`; `:48` `ShellDirectory`.
- `claude/.claude/scripts/lib/git_commit_calls.py:148,249` — `git_call_commits`, `git_commit_dirs`.
- `claude/.claude/scripts/lib/file_lock.py:17` — `hold_exclusive`.
- `claude/.claude/scripts/lib/file_backup.py:23` — `save_files`; `:50` `restore_missing`; `:66` `restore_changed`; `:82` `discard`.
- `claude/.claude/scripts/gates/calibration_guard.py:100` — `main`; `:72` `lock_is_live`.
- `claude/.claude/agents/mutation-tester.md:23-117` — Steps 0 to 4.
- `claude/.claude/skills/guide/SKILL.md:16` — commands; `:79` blocks; `:100` fields.
- `claude/.claude/skills/refactor/SKILL.md:64` — `log` call and input keys.
- `claude/.claude/skills/refactor/scripts/refactor_flow.py:709` — `validate_log`; `:1063` `parse_arguments`; `:1085` `main`.
- `tests/scripts/test_git_discipline_gate.py:21,952` — `GateCaseBase`, `PushReviewedTreeTest`.
- `tests/scripts/test_refactor_flow.py:342` — skill JSON example test.
- `tests/scripts/toolkit_paths.py:11-26` — path constants.
- `tests/run.sh`, `tests/lint.sh`, `tests/parallel_tests.py`, `tests/changed_scope.py` — suite entry points.
- `~/agent-evals/bin/rule_meter.py:1435` — `grade`; `:2671` `main`; `:1578` `load_scenarios`.

## Patterns Found

- Hook gates: stdin JSON, `hook_input.run_gate(main)`, deny through `hook_input.emit_decision("deny", ...)`, internal errors fail closed; `import_guard.guard(name, __name__)` before toolkit imports.
- Gate tests: a `GateCaseBase` with subprocess runs of the script, a temp `HOME`, and script path from an env var defaulting to a `toolkit_paths` constant.
- Directory placement for git calls is owned by `lib/git_calls.py`; callers read `GitCall.directory` and `.subcommand`.
- `refactor_flow.py`: argparse subparsers, one `RefactorFlowError` class, errors to stderr as `refactor-flow: <msg>`, exit 1; outputs end in `NEXT:` or `STOP:`; skill examples are parsed by a test.
- Mutation lock and backup are shell snippets in agent prose with jq; the lock reader is a Python SessionStart hook.
- opencode ports are full-text copies with frontmatter and wording differences; skills load from `~/.claude/skills` rather than being copied.
- Prose tests: files that open skill or agent markdown are listed in `changed_scope.PROMPT_READING_TESTS` and kept honest by `test_prompt_reader_list.py`.
- rule-meter: scenario JSON keyed by rule id with a `detector` name; detectors are `detect_*` functions or hidden checks in `rule_meter_checks/`.

## Reuse Inventory

- `hold_exclusive(lock_path, timeout_seconds)` -> context manager — `claude/.claude/scripts/lib/file_lock.py:17` — exclusive flock with timeout; raises `LockTimeoutError`.
- `save_files(root, paths, backup_dir, max_file_bytes=MAX_FILE_BYTES)` -> `Backup` — `lib/file_backup.py:23` — copy files under a backup folder.
- `restore_missing(backup)` -> `(restored, lost)` — `lib/file_backup.py:50`.
- `restore_changed(backup)` -> sorted paths — `lib/file_backup.py:66`.
- `discard(backup)` -> None — `lib/file_backup.py:82`.
- `write_text_atomically(path, content)` — `lib/script_utils.py:1357`; `state_file_path(state_dir, name, suffix)` — `:1397`; `read_jsonl(path)` — `:1441`; `repo_root(cwd, timeout=None)` — `:594`; `read_ledger(args, wait_seconds)` — `:748`.
- `git_calls(command, directory=".", context=NO_CONTEXT)` -> list of `GitCall` — `lib/git_calls.py:396`; `is_linked_worktree(call)` — `:243`.
- `git_options(words)`, `command_after_wrappers(words, peel_containers=True)`, `step_words(command)`, `segment_words(segment)`, `git_c_directory(words, directory)` — `lib/shell_command.py:550,632,714,724,958`.
- `cd_folder(words)`, `ShellDirectory` — `lib/shell_directory.py:33,48`.
- `push_review_state(repo_dir)` -> `PUSH_NO_RECORD | PUSH_REVIEWED | PUSH_CHANGED` — `lib/reviewed_tree.py:324`; `tree_fingerprint` `:86`; `record_shared_base(top, head, tree_hash)` `:314`; `record_reviewed` `:364`.
- `lock_is_live(stamp, owner_pid, now, writer="", session_pid="")` — `gates/calibration_guard.py:72`.
- `validate_log(mode, refactor_log)` — `refactor_flow.py:709`; `read_refactor_log(path)` — `:806`; `next_line(text)` — `:283`.
- Test helpers: `GateCaseBase` (`tests/scripts/test_git_discipline_gate.py:21`) with `repo_on`, `run_raw`, `run_command`, `write_transcript`, `typed_prompt`, `reason_of`; `load_reviewed_tree()` (`:943`); `toolkit_paths.first_python_that_starts(names)` (`tests/scripts/toolkit_paths.py:42`) and the path constants.
- Suite tools: `tests/changed_scope.py` (`scope`, `kept`), `tests/review_gate_unchanged.py` (`snapshot`, `compare`), `tests/duplicate_code.py`.
- rule-meter: `grade(scenario, tool_calls, tree, base_sha, result_text=None)` — `~/agent-evals/bin/rule_meter.py:1435`; `load_scenarios()` — `:1578`; `run_cell(rule, level, arm, run, scenarios, dry_run, record=None)` — `:2488`.
