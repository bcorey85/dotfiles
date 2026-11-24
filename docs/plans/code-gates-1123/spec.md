# code-gates-1123: rg cuts a check's output, background-aware announced step, /code fork review gate

> Research: ./02-research.md (goal-blind, produced before design began)
> Decisions: ./03-decisions.md (the design-resolution ledger)
> Date: 2026-11-23

<!-- Source precedence: on anything concrete, THIS file wins over the ledger (which records why, not what). A disagreement between them is a spec bug — report it. -->

## Summary

This plan fixes three toolkit defects from the agent-evals queue:

- `quality_check_cap.py` counts a check piped into `rg` as cut, so the one redirected rerun is allowed.
- The announced-step stop gate passes a subjectless progress line ("a new agent is working on it") when the same turn launched background work. A crash in one stop check no longer drops the other checks' reasons.
- A `/code` fork that dispatched a coder and ends with no review and no `stop.md` is sent back once at SubagentStop, or denied at SubagentHandback.

Item 3 of the ticket (inline python heredoc) left this plan per ledger block 5. Its Done-when is not met by this branch.

## Phase Status

- [x] Phase 1: quality-check-cap counts rg as cutting output (risk: low)
- [x] Phase 2: announced-step passes a subjectless progress line after a background launch in the same turn (risk: low)
- [x] Phase 3: /code run names and script call arguments have one owner (risk: low)
- [ ] Phase 4: a /code fork that coded a phase but never reviewed it is sent back at SubagentStop and denied at SubagentHandback (risk: high)
- [ ] Phase 5: Close pass — /close-branch parallel review, one fix, fix-diff gate, recap (risk: high)

## Plan Deviations

- ruling: Ticket #2, Phase 2: an Agent call counts as a background launch unless `run_in_background` is explicitly false (the Agent tool runs in the background by default; real transcripts: 332 of 338 keyless Agent calls returned an async launch result). Bash still needs `run_in_background` true. By the orchestrating /code session, 2026-11-24.
- ruling: Ticket #2, Phase 2: `runs_in_background` and `launches_background` live in new stdlib-only `lib/tool_call_flags.py` (not in script_utils), so the PreToolUse gates do not load script_utils; wait_loop_gate.py and inline_interpreter_hint.py now read it, so both accept the string "true" as background. By the orchestrating /code session, 2026-11-24.
- ruling: Ticket #2, Phase 2 ask rejected: a launch whose tool_result is a hook error still counts as a launch. No session hit it (2 such calls in 300 transcripts); size rule. By the lane session, 2026-11-24.
- ruling: Phase 2 review reached its 5-round cap; the one finding open at the cap (a stale announced_step.py docstring) was fixed, and the branch-end full suite covers the final tree. Committed without a sixth round. By the lane session, 2026-11-24.
- ruling: Phase 3 review reached its 5-round cap with round 5 clean; the fix passes also moved the wait command into code_wait.py and code_review_start.py through code_run_names. Ask rejected: `PHASE_START_SCRIPT` and the code_run_names docstring stay, since Phase 4 reads them. By the lane session, 2026-11-24.

## Decisions

1. Item 1 check site — one reader, `lib/fork_review.py`, called from `gates/staged_claim_gate.py` on SubagentStop and from the code-fork branch of `code/coder_gate.py hook` on PreToolUse SubagentHandback (already registered; no settings.json edit). Trade-off: a fork whose transcript cannot be read ends unjudged (fail open).
2. Item 1 freshness — the fork's own transcript decides; the run folder is never read.
3. Item 1 anchor and recorded reason — the transcript is split into segments at each `phase_start.py` call; a segment with a coder dispatch needs, after its first coder dispatch, review start then wait review, or a `stop.md` write. A tick coder after the review needs no second review.
4. Item 2 fix — subjectless progress forms pass only when the turn launched a Bash or Agent call with `run_in_background` true (bool or string); first-person forms still block; each stop check gets its own crash guard.
5. Item 3 — left the plan (agent-evals-c3-owner, 2026-11-23: the auto-mode gate pilot is a live experiment).
6. Item 4 readers — add `rg` only. Trade-off: sed and awk still read as seen in full.
7. Item 2 turn boundary — the latest record that opens a turn (typed prompt, `!` echo, task notification, peer message).

## Approaches Considered and Not Taken

- Item 2: exempt any open background work in the session. It passes correct blocks wherever older background work is still open (02-research.md).
- Item 1: pass when the run folder holds a review packet. The folder holds leftovers from earlier runs, so a stale packet passes.
- Item 1: anchor on the last coder dispatch. A tick coder after a converged review would demand a second review.
- Item 1: leave the hand-back ending unjudged. It leaves AC1 (a check fails a /code fork's hand-back) open for forks that end through SubagentHandback.
- Item 3: restore `shell_write_gate.py` / `interpreter_writes.py` from `d1b7a463d^`. It reverses the user's 2026-11-21 removal.

## Constraints

- Scripts run on Python 3.10 (`exercised`: repo rule in `claude/.claude/scripts/CLAUDE.md`).
- No edits to `claude/.claude/settings.json`, `claude/.claude/scripts/review/`, agents, `skills/code/SKILL.md`, or any CLAUDE.md.
- `code_step.py` does not exist (removed in 7b347d962). /code runs as prompt steps in `skills/code/SKILL.md`. Step 5 already says to review every phase (`exercised`).
- `announced_step.ANNOUNCEMENT` already passes "is running" through `WORK_RUNS`. The incident sentence was "Next queue item: a new agent is working on it." (`exercised`: session f5a1cc30, block at 2026-11-24T03:20:11Z).
- The incident turn opened at 2026-11-24T03:19:26Z on a `<bash-input>` echo. Its Bash launch had `run_in_background: true` and its Agent launch had `run_in_background: "true"` as a string (`exercised`).
- About 92% of code-fork endings are a final text reply, which only SubagentStop sees (`exercised`: 1738 transcripts). The rest end through SubagentHandback, which `code/coder_gate.py hook` sees on PreToolUse (`exercised`).
- A `/code` fork's first record starts `Base directory for this skill: <path>/skills/code` (`exercised`: 1337 of 1754 code-fork transcripts).
- Shell parsing goes through `lib/shell_command.py` / `lib/shell_command_words.py`. Never use a bare split or regex on a command.
- A gate names its fail mode in a comment and never swallows an exception: it reports on stderr.
- Tests read script paths through `tests/scripts/toolkit_paths.py`.

## External Contracts

- **Claude Code Stop / SubagentStop hook.** The input carries `hook_event_name`, `stop_hook_active`, `last_assistant_message`, `transcript_path` and `cwd`. On SubagentStop it also carries `agent_type`, `agent_id` and `agent_transcript_path`. Stdout `{"decision": "block", "reason": ...}` sends the turn back. Status:
  - Stop fields: `exercised`, read by `staged_claim_gate.py` today.
  - SubagentStop `agent_type` and `agent_transcript_path`: `declared-only`. No event has been captured, and Phase 4's tests use a synthetic payload. The reader falls back to the agent meta file (`agentType`) and to `script_utils.agent_transcript_path`.
  - The block reaching a fork: `exercised`. Old code_step-era SubagentStop block text appears in fork transcripts.
  - Before rollout: the user's smoke check in Phase 4's Manual Verification runs the real event.
- **Claude Code PreToolUse SubagentHandback hook.** The input carries `hook_event_name`, `tool_name`, `agent_type`, `agent_id`, `agent_transcript_path`, `session_id`, `cwd` and `tool_input` (`exercised`: test_open_child_gate.py and test_coder_gate.py events; `code/coder_gate.py hook` is registered on it in settings.json). A `permissionDecision` deny on stdout refuses the hand-back.
- **`stop_hook_active`.** It is true on a stop that follows a block. It prevents a block loop (`exercised`).

## Approach

- **Item 4:** a one-token regex change plus the deny text, in `gates/quality_check_cap.py`.
- **Item 2:**
  - Turn and background readers go in their owners: `lib/user_prompts.py` (`starts_turn`) and `lib/script_utils.py` (`runs_in_background`, `turn_launched_background`).
  - `gates/announced_step.py` splits its regex into first-person and progress forms. It reads the transcript only when a progress form survives the existing filters.
  - `gates/staged_claim_gate.py` runs each check through `guarded`, which reports a crash on stderr and keeps the other reasons.
- **Item 1:**
  - The new no-import name module `lib/code_run_names.py` is the owner of the /code script and verb names.
  - A new `lib/shell_command_words.py` `script_call_arguments` returns the words after a script's own word. `code/coder_gate.py` `runs_script` becomes its caller.
  - The new `lib/fork_review.py` reads the fork transcript once, in phase segments. `staged_claim_gate.py` calls it on SubagentStop, and the code-fork branch of `coder_gate.py hook` calls it on PreToolUse SubagentHandback.

## Dependencies

- No packages.
- Internal modules:
  - `lib/script_utils.py`: `tool_use_calls`, `agent_transcript_path`, `FORK_AGENT_TYPE`, `bash_commands` as the scan shape.
  - `lib/loop_transcript.py`: `call_paths`, `agent_meta`.
  - `lib/stop_file_names.py`: `STOP_FILE`.
  - `lib/shell_command.py`: `resolved_command_words`.
  - `lib/shell_command_words.py`: `word_names_command`.
  - `lib/user_prompts.py`.

## Implementation Plan

## Phase 1: quality-check-cap counts rg as cutting output

### Overview

A check piped into `rg` is recorded as cut, so one rerun redirected to a file is allowed. Size estimate: about 30 changed lines.

### Changes Required:

#### 1. Gate

**File**: `claude/.claude/scripts/gates/quality_check_cap.py`

**Changes**:
- At :92, `OUTPUT_FILTER_START = re.compile("^(tail|head|grep|rg)(" + WS + "|$)")`.
- `CUT_DENY_TEXT` (:104-107) names "tail, head, grep or rg" in both places.
- The module docstring, the comment near :96 and the `cuts_output` docstring name rg too.

#### 2. Tests

**File**: `tests/scripts/test_quality_check_cap.py`

**Changes**:
- In the cut section (about :727), add `test_rg_cuts_the_output_too`. It runs one subTest for each cut: `| rg '^(Ran|OK|FAILED)'`, `2>&1 | rg -A 3 FAILED`, `| rg`, and the incident shape `python3 -m unittest discover -s tests 2>&1 | rg '^(Ran|OK|FAILED)'`. Each subTest uses its own check command.
- In each subTest:
  - `post` the piped run;
  - `assert_allowed` a rerun of the same check with `> /tmp/check.log 2>&1`;
  - `assert_denied` a bare rerun, and assert that its deny text names `rg`. This covers AC15 (a second rerun with no redirect is still denied) and AC16 (the deny message says tail, head, grep or rg cut the output).
- Update any test that asserts the old `CUT_DENY_TEXT` words.

#### 3. Change file

Run `python3 ~/agent-evals/bin/build_changes.py new "quality check cap counts a check piped into rg as cut" --by claude-code/claude-opus-5-5 --root /home/brandon/dotfiles-code-gates-nov23/docs/changes`. Then fill the file it prints, and rerun with the same `--root`.

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_quality_check_cap.py` (RED before the fix: `test_rg_cuts_the_output_too` fails while line 92 lists only tail, head and grep)
- [ ] **Lint-verified**: `bash tests/lint.sh claude/.claude/scripts/gates/quality_check_cap.py tests/scripts/test_quality_check_cap.py`

#### Manual Verification:

- [ ] N/A (covered by the hook test)

## Phase 2: announced-step passes a subjectless progress line after a background launch in the same turn

### Overview

The subjectless progress forms pass when the current turn launched background work. First-person forms still block. A crash in one stop check keeps the other checks' reasons. Size estimate: about 185 changed lines.

### Changes Required:

#### 1. Turn start

**File**: `claude/.claude/scripts/lib/user_prompts.py`

**Changes**: add `starts_turn(record)`. It is True for a main-session record when all of these hold:
- `type == "user"`;
- the record is not `isSidechain`, `isMeta` or `isCompactSummary`;
- `message.content` is a string, or a list that holds no `tool_result` block.

That covers typed prompts, `<bash-input>` / `<bash-stdout>` echoes, task notifications and peer messages. Update the module docstring.

#### 2. Background launch readers

**File**: `claude/.claude/scripts/lib/script_utils.py`, beside `tool_use_calls` and `bash_commands`.

**Changes**:
- `runs_in_background(tool_input)`: reads `tool_input.get("run_in_background")`. True when the value is `True`, or a string whose `.strip().lower()` is `"true"`.
- `turn_launched_background(transcript_path)`:
  - Make one pass over the file, opened with `errors="replace"`.
  - Read each line with `json.loads` inside a try that skips a ValueError.
  - A `starts_turn` record resets the flag to False.
  - A `Bash` or `Agent` call from `tool_use_calls(line)` whose input passes `runs_in_background` sets the flag to True.
  - Return the flag. Return False on OSError or an empty path.

#### 3. Announced step

**File**: `claude/.claude/scripts/gates/announced_step.py`

**Changes**:
- Split `ANNOUNCEMENT` into two regexes:
  - `FIRST_PERSON_ANNOUNCEMENT`: every `I'll`, `I will`, `I'm ...` and `I am ...` form.
  - `PROGRESS_ANNOUNCEMENT`: `starting\s+(?:it|that|this|on\s+it|work)\s+now|on\s+it\s+now|working\s+on\s+it`.
- Keep `ANNOUNCEMENT` as their union for `without_quoted_spans`.
- The signature becomes `announced_step(message, transcript_path=None)`. After the existing filters, for each sentence:
  - A `FIRST_PERSON_ANNOUNCEMENT` match returns the sentence.
  - For a progress-only match, compute `script_utils.turn_launched_background(transcript_path)` lazily, at most once per call. When it is True, go to the next sentence. Otherwise return the sentence.
- "I'm on it now" and "I'm working on it" still block.
- Add the `sys.path` and import lines as staged_claim_gate sets them.
- Update the docstring.

#### 4. Per-check crash guard

**File**: `claude/.claude/scripts/gates/staged_claim_gate.py`

**Changes**:
- Add `guarded(name, check, *args)`. It returns `check(*args)`. On an Exception it prints `staged-claim-gate: {name} skipped: {type(error).__name__}: {error}` to stderr and returns None. Its comment says it fails open per check.
- In `main()`, run each check through `guarded`: `staged_claim_reason`, the permission-question block and `announced_step.announced_step(message, hook.get("transcript_path"))`.
- Replace the bottom `contextlib.suppress(Exception)` with a try/except that prints `staged-claim-gate: skipped: ...` to stderr.
- Update the docstring's fail-open sentence.

#### 5. Tests

**New file**: `tests/scripts/test_user_prompts.py`.
- `starts_turn` is True for a typed prompt, a `<bash-input>` echo and a `<task-notification>` string. It is False for a tool_result list, an `isMeta` record and an `isSidechain` record.
- `turn_launched_background`:
  - resets at a turn start;
  - accepts `True` and `"true"`, and rejects `False` and `"false"`;
  - skips a torn last line;
  - returns False for a missing file.

**File**: `tests/scripts/test_announced_step.py`.
- `run_gate` gains a `transcript_path` argument.
- A builder writes a transcript: a turn-start `<bash-input>` echo record, then assistant records with `Bash` (`run_in_background: True`) and `Agent` (`run_in_background: "true"`).
- Cases:
  - `test_incident_progress_line_after_a_background_launch_passes`: "Next queue item: a new agent is working on it." passes. RED before the fix.
  - `test_suite_is_running_after_a_background_launch_passes`: "The dotfiles suite is running on it now." passes.
  - `test_progress_line_with_the_launch_in_an_earlier_turn_blocks`: a second turn-start record after the launches.
  - `test_progress_line_with_no_transcript_blocks`: "Starting it now." with `transcript_path ""`.
  - `test_first_person_step_after_a_background_launch_still_blocks`: "I'll push them with the four closures at the end."
  - `test_torn_last_line_still_reads_the_turn`: `{"type": "assi` is appended, and the incident sentence still passes.

**File**: `tests/scripts/test_staged_claim_gate.py`. Add `test_a_crash_in_one_check_keeps_the_staged_claim_reason`:
- Load the gate in-process.
- Patch `announced_step.announced_step` to raise.
- Feed a staged claim against an empty index.
- Assert that stdout blocks with the staged reason and that stderr names `announced_step skipped`.

#### 6. Real blocks and change file

- With a scratchpad script, find every past block of this gate: search `~/.claude/projects/**/*.jsonl` for the text of `announced_step.REASON`. For each block, take the `last_assistant_message` before it and the transcript cut at the block's line. Run the new `announced_step` on that pair.
- Report "N of M still block". Read each block that now passes by hand and label it either:
  - incident shape: a progress form, with a background launch in the same turn;
  - gate gap: anything else.
- Any gate gap stops the phase for a report before review.
- Change file: `python3 ~/agent-evals/bin/build_changes.py new "announced step passes a progress line after a background launch in the same turn" --by claude-code/claude-opus-5-5 --root /home/brandon/dotfiles-code-gates-nov23/docs/changes`. Fill it, then rerun with the same `--root`.

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_announced_step.py` (RED before the fix: the incident case fails)
- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_user_prompts.py` (RED now: no file)
- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_staged_claim_gate.py` (RED now: no crash-guard case)
- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_script_utils.py`
- [ ] **Lint-verified**: `bash tests/lint.sh claude/.claude/scripts/gates/announced_step.py claude/.claude/scripts/gates/staged_claim_gate.py claude/.claude/scripts/lib/user_prompts.py claude/.claude/scripts/lib/script_utils.py tests/scripts/test_announced_step.py tests/scripts/test_user_prompts.py tests/scripts/test_staged_claim_gate.py`
- [ ] **Agent-run**: the sweep reports "N of M still block" over every past block found by the REASON text, and every block that now passes is labelled incident shape or gate gap (no gate gap)

#### Manual Verification:

- [ ] N/A (covered by the hook tests)

## Phase 3: /code run names and script call arguments have one owner

### Overview

The script names that /code's review step runs, and a shell reader for a script's call arguments, each get one owner in lib. fork_children, code_wait and coder_gate import them. No behavior changes.

Size estimate: about 60 changed lines.

### Changes Required:

#### 1. Name owner

**New file**: `claude/.claude/scripts/lib/code_run_names.py`. It imports nothing. Constants:
- `PHASE_START_SCRIPT = "phase_start.py"`
- `REVIEW_START_SCRIPT = "code_review_start.py"`
- `WAIT_SCRIPT = "code_wait.py"`
- `WAIT_REVIEW_VERB = "review"`

Its docstring says the fork review reader runs at SubagentStop and in the hand-back hook, so it reads these names here and must not load review/.

#### 2. Script call arguments

**File**: `claude/.claude/scripts/lib/shell_command_words.py`

**Changes**: add `script_call_arguments(command, script_name)`.
- For each word list in `shell_command.resolved_command_words(command)`, find the first word `w` where `word_names_command(w, script_name)` holds, and record the words after it.
- Return one list per simple command that runs the script.
- Add the name to the module docstring.

#### 3. Callers take the names

- `claude/.claude/scripts/code/fork_children.py:41`: `from code_run_names import REVIEW_START_SCRIPT`. The name stays importable from fork_children.
- `claude/.claude/scripts/code/code_wait.py:681`: compare against `code_run_names.WAIT_REVIEW_VERB`.
- `claude/.claude/scripts/code/coder_gate.py`: `runs_script` (:726) becomes `return bool(shell_command_words.script_call_arguments(command, script_name))`. The `"coder"` literals stay as they are.
- `tests/scripts/toolkit_paths.py`: add `"shell_command_words.py"` and `"code_run_names.py"` to `CODER_GATE_LIB_MODULES`, unless they are already there.

#### 4. Tests

**File**: `tests/scripts/test_shell_command_words.py`. Add `script_call_arguments` cases:
- `python3 ~/.claude/scripts/code/code_wait.py review` gives `[["review"]]`.
- A `cd r && python3 /x/code_review_start.py code - 1 h --detach && python3 /x/code_wait.py review` chain gives one hit for each script.
- `python3 ~/.claude/scripts/code/phase_start.py --new-run` gives `[["--new-run"]]`. Bare `phase_start.py` gives `[[]]`.

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_shell_command_words.py` (RED now: no `script_call_arguments`)
- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_coder_gate.py`
- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_fork_children.py`
- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_code_wait.py`
- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_telemetry_switch.py` (it copies `CODER_GATE_LIB_MODULES`)
- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_import_guard.py` (it runs `coder_gate.py` from a copied tree)
- [ ] **Lint-verified**: `bash tests/lint.sh claude/.claude/scripts/lib/code_run_names.py claude/.claude/scripts/lib/shell_command_words.py claude/.claude/scripts/code/coder_gate.py claude/.claude/scripts/code/code_wait.py claude/.claude/scripts/code/fork_children.py tests/scripts/test_shell_command_words.py tests/scripts/toolkit_paths.py`

#### Manual Verification:

- [ ] N/A (no behavior change)

## Phase 4: a /code fork that coded a phase but never reviewed it is sent back at SubagentStop and denied at SubagentHandback

### Overview

A `code-fork` whose first record names `/skills/code` is judged per phase segment. Its transcript is split at each `phase_start.py` call; a transcript with no such call is one segment. A segment that holds a coder dispatch needs one of these after its first coder dispatch:
- a `code_review_start.py` call followed by a `code_wait.py review` call;
- or a `stop.md` write.

A fork that fails this check is handled by how it ends:
- A final text reply is sent back once at SubagentStop.
- A SubagentHandback call is denied in PreToolUse, with the same reason.

Writing `stop.md` always clears the deny.

Size estimate: about 330 changed lines plus one fixture.

### Changes Required:

#### 1. The reader

**New file**: `claude/.claude/scripts/lib/fork_review.py`. It lives in lib because coder_gate.py adds only `lib` and `telemetry` to sys.path. It imports lib modules only: script_utils, loop_transcript, shell_command_words, code_run_names, stop_file_names.

- `SKILL_BASE = re.compile(r"\ABase directory for this skill: \S*/skills/code\s*\n")`.
- `Segment` NamedTuple: `coder_line`, `review_start_lines`, `review_wait_lines`, `stop_lines`. `ForkReview` NamedTuple: `is_code_run`, `segments` (a list of Segment).
- `read_fork_review(transcript_path)`:
  - Make one pass, opened with `errors="replace"`. Read each line with `json.loads` in a try, so a torn line is skipped.
  - `is_code_run` is True when the first record's string content matches `SKILL_BASE`.
  - A `Bash` call where `script_call_arguments(command, PHASE_START_SCRIPT)` is non-empty opens a new segment. The records before the first such call form segment 0.
  - In the current segment:
    - The first `Agent` call whose `subagent_type` is in `script_utils.CODERS` sets `coder_line`.
    - For `Bash` calls, `script_call_arguments` finds `REVIEW_START_SCRIPT` (any arguments) and `WAIT_SCRIPT` with first argument `WAIT_REVIEW_VERB`.
    - Paths from `loop_transcript.call_paths(line)` whose basename is `STOP_FILE` go to `stop_lines`.
- `segment_reviewed(segment)` is True when any of these holds:
  - `coder_line is None`;
  - a stop line comes after `coder_line`;
  - a start line comes after `coder_line`, and a wait line comes at or after that start.

  A tick coder dispatched after the converged review comes after `coder_line`, so it needs no second review.
- `reviewed(fork_review)` is True when every segment is reviewed.
- `missing_review_reason(hook)` returns `REASON` or None. It returns None when any of these holds:
  - the agent type is not `script_utils.FORK_AGENT_TYPE`. Read the type from `hook["agent_type"]`, or else from `loop_transcript.agent_meta(path)["agentType"]`, with the transcript path from `script_utils.agent_transcript_path(hook)`;
  - the transcript is missing or cannot be read (fail open);
  - the fork is not a code run;
  - the fork reviewed.

  It does not check the event name. Each caller checks it.
- `REASON`: "This /code run dispatched a coder for a phase but ran no review of it and wrote no stop. Run step 5 of the /code skill now: write the handoff block to `<run folder>/handoff.txt`, run `python3 ~/.claude/scripts/code/code_review_start.py <lane> - 1 <run folder>/handoff.txt --base <phase base> --detach` (the plan path and phase number in place of `- 1` when the run has a plan), then `python3 ~/.claude/scripts/code/code_wait.py review`. If the run must stop before its review, write the stop to `<run folder>/stop.md` first."
- The docstring says:
  - the reader fails open;
  - it never reads the run folder;
  - its two callers;
  - the fields each event supplies: PreToolUse SubagentHandback `agent_type` and `agent_transcript_path` are `exercised` (test_open_child_gate.py, test_coder_gate.py); the SubagentStop field names come from no captured event.

#### 2. Stop gate caller

**File**: `claude/.claude/scripts/gates/staged_claim_gate.py`

**Changes**:
- When `hook_event_name == "SubagentStop"`, append `guarded("fork_review", fork_review.missing_review_reason, hook)`. It blocks once per stop, through `stop_hook_active`.
- Import `fork_review` at the top.
- Add one docstring sentence.

#### 3. Hand-back caller

**File**: `claude/.claude/scripts/code/coder_gate.py`, `run_hook` (:871)

**Changes**: after `event = json.load(sys.stdin)` and before the `agent_type != "coder"` check, add:

    if event.get("agent_type") == script_utils.FORK_AGENT_TYPE:
        reason = fork_review.missing_review_reason(event)
        if reason:
            script_utils.pre_tool_use_deny(reason)
        return

- Import `fork_review` at the top.
- This hook is already registered on PreToolUse `SubagentHandback` (timeout 3600), so settings.json is not edited.
- The deny repeats on each hand-back until a review or a stop.md write appears. A crash blocks the hand-back through `hook_input.run_gate`, as the coder branch does today.
- Add `"fork_review.py"`, `"loop_transcript.py"`, `"stop_file_names.py"` and any other lib module the copied gate now imports to `CODER_GATE_LIB_MODULES` in `tests/scripts/toolkit_paths.py`, unless they are already there.

#### 4. Fixture and tests

**New fixture**: `tests/scripts/fixtures/code_fork_no_review.jsonl`. It is a trimmed copy of `~/.claude/projects/-home-brandon-agent-evals/74021271-80fa-4df9-9ce4-9e067e2847ee/subagents/agent-af3a946da2498ee41.jsonl`, keeping these records in order:
- the first user record, cut to the skill-base line plus `# Code\n`;
- the queue-read Bash call;
- the coder Agent call and its "Async agent launched" result;
- the `code_wait.py agent <id>` call;
- the `git status` call;
- the final text record.

Keep the real record keys. Replace queue-item text and paths outside `/home/brandon/agent-evals` with placeholders.

**New test file**: `tests/scripts/test_fork_review_gate.py`.
- It runs `toolkit_paths.GATES_DIR / "staged_claim_gate.py"` as a subprocess with this synthetic payload: `{"hook_event_name": "SubagentStop", "agent_type": "code-fork", "agent_id": "af3a946da2498ee41", "agent_transcript_path": <tmp copy>, "session_id": "s1", "cwd": <tmp>, "stop_hook_active": false, "last_assistant_message": "Done."}`.
- A top comment marks the payload SYNTHETIC.
- Cases:
  - `test_incident_fork_with_a_coder_and_no_review_is_sent_back`: RED before the fix.
  - `test_fork_that_ran_review_start_then_wait_review_passes`
  - `test_review_start_and_wait_in_one_call_passes`: the `&&` form.
  - `test_review_start_without_wait_is_sent_back`
  - `test_review_before_the_coder_dispatch_is_sent_back`
  - `test_stop_md_written_after_the_coder_passes`: a Write to `<git dir>/code-phase/stop.md`.
  - `test_stale_stop_md_before_the_coder_is_sent_back`: a stop.md Write, then the coder dispatch, then the end (AC6).
  - `test_stale_run_folder_with_review_out_and_stop_md_is_sent_back`: the run folder on disk holds `review.out` and `stop.md`, the transcript shows neither after the coder, and the fork is sent back (AC6).
  - `test_multi_phase_second_phase_coded_without_review_is_sent_back`: `phase_start.py --new-run`, coder, review start, wait review, `phase_start.py`, coder, end.
  - `test_multi_phase_every_phase_reviewed_passes`: the same with a review in the second segment.
  - `test_tick_coder_after_the_review_passes`: coder, review start, wait review, then a second coder dispatch in the same segment.
  - `test_fork_with_no_coder_dispatch_passes`
  - `test_review_and_fix_forks_pass`: the first record names `/skills/review`, and separately `/skills/fix`.
  - `test_other_agent_type_passes`: `coder`.
  - `test_agent_type_read_from_meta_when_the_event_lacks_it`: an `agent-<id>.meta.json` holding `{"agentType": "code-fork"}`. The fork is sent back.
  - `test_second_stop_passes`: `stop_hook_active: true`.
  - `test_main_session_stop_never_runs_the_fork_check`
  - `test_missing_transcript_passes`
  - `test_torn_last_line_is_skipped`

**File**: `tests/scripts/test_coder_gate.py`. Add hand-back cases that run `coder_gate.py hook` with `{"hook_event_name": "PreToolUse", "tool_name": "SubagentHandback", "agent_type": "code-fork", "agent_id": "f1", "agent_transcript_path": <tmp copy of the fixture>, "session_id": "s1", "cwd": <tmp>, "tool_input": {"message": "done"}}`:
- `test_code_fork_handback_with_no_review_is_denied`: stdout is a PreToolUse deny that carries `fork_review.REASON`. RED before the fix.
- `test_code_fork_handback_after_a_stop_md_write_passes`: the fixture plus a stop.md Write after the coder. Empty stdout.
- `test_code_fork_handback_never_reads_the_coder_gate_file`: a gate file is set for the cwd, the fork reviewed, and stdout is empty (no stamp).

#### 5. Real-input sweep and change file

- With a scratchpad script, run `read_fork_review` and `reviewed` over every `~/.claude/projects/**/subagents/agent-*.jsonl` whose meta `agentType` is `code-fork`. Report:
  - "parsed N of M";
  - the `/code` run count;
  - the multi-segment count;
  - the sent-back count, split by how the fork ended (final text reply vs SubagentHandback call);
  - 5 sent-back paths, read by hand and labelled true miss or gate gap.
- If more than 10% of `/code` forks would be sent back, stop and report before review.
- Change file: `python3 ~/agent-evals/bin/build_changes.py new "a code fork that coded a phase and ran no review is sent back at SubagentStop and denied at SubagentHandback" --by claude-code/claude-opus-5-5 --root /home/brandon/dotfiles-code-gates-nov23/docs/changes`. Fill it, then rerun with the same `--root`.

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_fork_review_gate.py` (RED now: no file)
- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_coder_gate.py` (RED now: no code-fork hand-back branch)
- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_staged_claim_gate.py`
- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_telemetry_switch.py` (it copies `CODER_GATE_LIB_MODULES`)
- [ ] **Test-verified**: `python3 tests/parallel_tests.py test_import_guard.py`
- [ ] **Lint-verified**: `bash tests/lint.sh claude/.claude/scripts/lib/fork_review.py claude/.claude/scripts/gates/staged_claim_gate.py claude/.claude/scripts/code/coder_gate.py tests/scripts/test_fork_review_gate.py tests/scripts/test_coder_gate.py tests/scripts/toolkit_paths.py`
- [ ] **Agent-run**: the sweep reports parsed N of M, the multi-segment count, the sent-back count by ending (at most 10% of /code forks), and 5 hand-read samples

#### Manual Verification:

- [ ] **Manual-verified**: in a live session, run `/code` on a one-line scratch task and tell the fork to end right after the coder returns. The fork gets one "ran no review of it and wrote no stop" block, then runs step 5 or writes stop.md. This checks the real SubagentStop fields.
- [ ] **Manual-verified**: run it again and tell the fork to end through SubagentHandback right after the coder returns. The hand-back is denied with the same reason, and passes after a stop.md write.

## Phase 5: Close pass

`/close-branch`: scripts first; four report-only reviewers in parallel on the whole branch diff (correctness, structure, test intent, and plan and acceptance-criteria reconciliation); one `coder` that fixes every finding and writes every owed test; a report-only gate on the fix diff alone; the recap sheet. Root-cause rule: a cast or default that papers over a fixable loose structure is a finding; fix the source.

### Success Criteria

Quality checks green; every reviewer finding fixed, shown wrong, or (an ask that changes a ticket AC) put to the user through agent-evals-c3-owner; the fix-diff gate passed; every acceptance criterion mapped to a test or explicitly retired; concentration counts stated; recap and smoke-test checklist delivered. With no open finding, a coder writes one line of evidence under each open item.

#### Automated Verification:

- [ ] **Suite**: `bash tests/run.sh`
- [ ] **Scope box**: `test -n "$(git diff --name-only <base-sha>..<head-sha>)"`, with the two recorded commit ids filled in at close

#### Manual Verification:

- [ ] N/A (close pass)
