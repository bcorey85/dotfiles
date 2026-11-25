# gate-false-positives-nov25: six gate and hook false positives or wrong messages

> Decisions: ./03-decisions.md
> Date: 2026-11-25

Scripts live in `claude/.claude/scripts/`; tests in `tests/scripts/`, paths from `tests/scripts/toolkit_paths.py`.
Every phase starts with a test that fails on the current tree. Run changed test files through
`python3 tests/parallel_tests.py <file>` and `bash tests/lint.sh <changed .py>`.

## Scope

- In: `gates/announced_step.py`, `gates/staged_claim_gate.py`, `lib/message_text.py`, `gates/permission_question.py`,
  `gates/rg_path_gate.py`, `gates/git_discipline_gate.py`, `lib/reviewed_tree.py` (one new read beside
  `push_review_state`), `lib/memory_cap_scope.py`, `gates/inline_interpreter_hint.py`, and their tests.
- Out: `review/` scripts, `skills/`, `settings.json`, any CLAUDE.md.

## Phase Status

- [ ] Phase 1: Stop-hook text checks: background report steps, draft blocks, tracker writes (risk: low)
- [ ] Phase 2: rg path gate rewrites a one-step no-path rg through updatedInput (risk: medium)
- [ ] Phase 3: push refusal names the review base; background-run text fits the host (risk: low)

## Phase 1: Stop-hook text checks

1. `gates/announced_step.py`: add `REPORT_STEP`, a regex of report verbs on background work (bring back, report,
   rank, summarize/summarise, collect, compile, relay, combine, with suffixes). In `announced_step`, a sentence that
   matches `FIRST_PERSON_ANNOUNCEMENT` and `REPORT_STEP` passes when `user_prompts.turn_launched_background` is true
   (read once, as the progress branch does). Every other first-person sentence returns as today. Update the module
   docstring.
2. `lib/message_text.py`: add `without_draft_blocks(text)`: the text with fenced blocks (a line opening with three or
   more backticks or tildes, up to the matching close or the end) and blockquote lines (`>` after optional spaces)
   removed. `announced_step` applies it before `without_quoted_spans`.
3. `gates/permission_question.py`: add the tracker-write branch to `OUTWARD_STEP` per D3, with `FILE_NAME_AFTER` after
   ticket words and `HOST_NAME_AFTER` plus the GitHub-product exclusion after a tracker name. Update the docstring.

#### Automated Verification

- [ ] **Announced step**: "I'll bring back the ranked list from the three scouts." passes after a background launch and blocks with none; a fenced or `>` draft holding "I am fixing the parser." passes; a plain promise outside the fence still blocks - `python3 tests/parallel_tests.py test_announced_step.py`
- [ ] **Permission question**: "Shall I add a Jira link from A to B?" and "Want me to label the ticket?" pass; local cases still block - `python3 tests/parallel_tests.py test_staged_claim_gate.py`

## Phase 2: rg path gate rewrites a one-step no-path rg

1. `gates/rg_path_gate.py`: when `hanging_rg` finds a call and the command (after `shell_code`) is one step of one
   simple command whose text equals the original command stripped, write
   `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow", "updatedInput": {**tool_input,
   "command": command.rstrip() + " ."}}}`. Otherwise keep today's deny with the fixed command. Steps come from
   `shell_command.split_command_steps`; no bare split.
2. State in a comment that the gate is fail-open. Report a crash on stderr with the gate name instead of `pass`.
3. Measure the hook's median wall time over 30 runs before and after, and `python3 -c pass` the same way; the numbers
   go in the item 4 change file.

#### Automated Verification

- [ ] **rg rewrite**: `rg foo` gives allow with `updatedInput.command` `rg foo .`; a piped rg gives no output; `rg foo && ls` keeps the deny - `python3 tests/parallel_tests.py test_rg_path_gate.py`

## Phase 3: push refusal names the base; background-run text fits the host

1. `lib/reviewed_tree.py`: add `latest_reviewed_base(repo_dir)`: the `base` of the newest dict entry in the repo's
   shared record, or None. Share the record read with `push_review_state` through one helper.
2. `gates/git_discipline_gate.py`: on `PUSH_CHANGED`, deny with
   `[git-discipline-gate] code changed since the last review: run /review base=<hash> on this branch, then push`;
   with no base, today's text.
3. `lib/memory_cap_scope.py`: `background_deny_text()` returns the text with the cap when `cap_available()`, else the
   same text naming run_in_background alone. `gates/inline_interpreter_hint.py` calls it. Drop the constant if no
   other caller reads it.

#### Automated Verification

- [ ] **Push base**: the changed-after-review deny names the reviewed commit as `base=` - `python3 tests/parallel_tests.py test_git_discipline_gate.py`
- [ ] **Host text**: with no cap the text names run_in_background and not systemd-run - `python3 tests/parallel_tests.py test_memory_cap_scope.py test_inline_interpreter_hint.py`
- [ ] **Suite** - `bash tests/run.sh`
