# gate-false-positives-nov25: nine gate and hook false positives or wrong messages

> Decisions: ./03-decisions.md
> Date: 2026-11-25

Scripts live in `claude/.claude/scripts/`; tests in `tests/scripts/`, paths from `tests/scripts/toolkit_paths.py`.
Every phase starts with a test that fails on the current tree. Run changed test files through
`python3 tests/parallel_tests.py <file>` and `bash tests/lint.sh <changed .py>`.

## Scope

- In: `gates/announced_step.py`, `gates/staged_claim_gate.py`, `lib/message_text.py`, `gates/permission_question.py`,
  `gates/rg_path_gate.py`, `gates/git_discipline_gate.py`, `lib/reviewed_tree.py` (one new read beside
  `push_review_state`), `lib/memory_cap_scope.py`, `gates/inline_interpreter_hint.py`, `review/handback.py` and `review/capped_review.py` (D7), and their tests.
- Out: other `review/` scripts, `skills/`, `settings.json`, any CLAUDE.md.

## Phase Status

- [x] Phase 1: Stop-hook text checks: background report steps, draft blocks, tracker writes (risk: low)
- [x] Phase 2: rg path gate rewrites a one-step no-path rg through updatedInput (risk: medium)
- [ ] Phase 3: push refusal names the review base; background-run text fits the host (risk: low)
- [ ] Phase 4: staged-claim gate passes a check of what is staged (risk: low)
- [ ] Phase 5: a capped review with a passed full check on the tree earns push credit (risk: medium)

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

1. `gates/rg_path_gate.py`: when `hanging_rg` finds a call, allow with `{"hookSpecificOutput": {"hookEventName":
   "PreToolUse", "permissionDecision": "allow", "updatedInput": {**tool_input, "command": command.rstrip() + " ."}}}`
   only when all hold: the command (after `shell_code`) is one step of one simple command whose text equals the
   original command stripped; it has no output redirection; its raw first word is exactly `rg`; it has no `$`
   or backtick outside single quotes that a backslash does not escape, no word that starts with an unquoted `~`, and no expanding word (`shell_expansion.unquoted_expanding_word`); and
   `hanging_rg(command + " .")` is None. Otherwise deny with the fixed command, or with `REASON_NO_FIX` and no fixed
   command when that command would still hang (a dangling option such as `rg foo -g`). Steps come from
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

## Phase 4: staged-claim gate passes a check of what is staged

1. `gates/staged_claim_gate.py`: per D8, a claim whose `is/are staged` follows `what`, `whatever` or `whichever`
   (the word right before it) is no index claim. Update the docstring.
2. Tests in `tests/scripts/test_staged_claim_gate.py`: "It checks the skill list against what is staged." passes with
   an empty index; a reply naming another worktree's staged files by its absolute path passes when that worktree's
   index holds them; "I staged the change." still blocks with an empty index.

#### Automated Verification

- [ ] **Staged claim**: the two replies pass and "I staged the change." blocks - `python3 tests/parallel_tests.py test_staged_claim_gate.py`

## Phase 5: a capped review with a passed full check on the tree earns push credit

1. `review/capped_review.py`: `effective_status` reads a cap-reached packet with no blocker, no open class and no
   unrun reviewer as `deferred` when `full_check_receipt.valid_receipt(repo)` returns a receipt (D9). A packet whose
   `full_check_tree` matches as today still reads `deferred`.
2. Tests: `effective_status` gives `deferred` for such a packet; an end-to-end test stores a cap-reached hand-back
   whose only open finding names a plan file, records it through `handback.record_clean_review`, commits a change
   under the plan directory, and the push check of `gates/git_discipline_gate.py` allows the push; a code commit after
   it is denied.

#### Automated Verification

- [ ] **Capped credit**: a capped packet with a passed full check on the tree reads deferred; the push passes after a plans-only commit and blocks after a code commit - `python3 tests/parallel_tests.py test_handback.py test_git_discipline_gate.py`

## Plan Deviations

- 2026-11-25, agent-evals-c3-owner ruling: Ticket #9's "the loop writes full_check_tree" is reworded in AC14 to "effective_status reads a valid full-check receipt" (D9).
