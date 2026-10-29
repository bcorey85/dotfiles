---
type: "Change"
change_type: "changed"
title: "Remove every duplicate in the toolkit scripts; fail on any repeat"
description: "The duplicate check dropped its baseline and now fails on any repeated function name or jscpd clone; 29 repeated names and 14 clones moved into lib/script_utils.py and lib/hook_input.py or got names of their own."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T18:33:18-05:00"}
seq: 7
kind: "user-rule"
components: ["script/script-utils", "script/hook-input", "script/code-step", "script/review-fix", "script/verify-common", "script/verify-prep", "script/verify-log", "script/refactor-flow", "script/adr-flow", "script/deferred-push-check", "script/git-discipline-gate", "script/stale-citation-gate", "script/shell-write-gate", "script/comment-bloat-gate", "script/dead-prose-gate", "script/log-agent-usage", "script/log-skill-use", "script/telemetry-enabled", "script/duplicate-code"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-25: why are you not fixing all dupes"
proof: []
unmeasured: ""
---

## Change

`tests/duplicate_code.py` has no baseline and fails on any repeat. `tests/duplicate_code_baseline.json` is gone. A
jscpd clone counts as import preamble when either side is only imports.

New in `lib/script_utils.py`: `run_command`, `run_or_raise`, `repo_root`, `current_branch`, `repo_name`,
`TIMEOUT_EXIT_CODE`, `COMMAND_NOT_FOUND_EXIT_CODE`, `REPO_NAME_SCRIPT`. New in `lib/hook_input.py`: `jq_output`,
`jq_field`, `tool_input_of`, `edited_file_path`, `read_file_text`, `prune_old_state_files`. The gates, telemetry,
code-step, review-fix, verify, refactor and adr scripts call them and keep no copy. Functions that shared a name but
did different work got names of their own (`require_branch`, `branch_fingerprint`, `load_fix_state`,
`strip_target_quotes`, and others).

The CI workflow also runs on `claude/.claude/hooks/**`, `claude/.claude/skills/*/scripts/**` and `ruff.toml`.

Behavior that moved:

- `review_fix` and `deferred_push_check` name a worktree by its main checkout (`tools/repo-name`).
- `deferred_push_check` exits silently on a detached HEAD.
- verify and refactor errors read "`cmd` failed: stderr or stdout"; refactor now stops on a missing git.

## Evidence

The user asked why the check kept a baseline of known repeats instead of fixing them.

## Result

`python3 tests/duplicate_code.py`: 0 repeated names, 0 clones. A planted `git_output` copy fails with exit 1.
`bash tests/run.sh`: 2058 tests in 55 files, 0 failed, ruff clean. `tests/scripts/test_duplicate_code.py` holds 8
tests.

Out of scope: the three generated security hooks (a regenerate overwrites edits), and extensionless bash scripts,
which jscpd does not read.

## Watch

None. No intake number reads script structure.

## Back-out

Revert the commit. The baseline file and the per-script copies come back.
