# Stop hook keeps the blocked reply, and passes steps gated on another party or a date

> Research: ./02-research.md (goal-blind, produced before design began)
> Decisions: ./03-decisions.md (the design-resolution ledger)
> Ticket: ./00-ticket.md
> Date: 2026-11-27

<!-- Source precedence: on anything concrete, THIS file wins over the ledger (which records why, not what). A disagreement between them is a spec bug — report it. -->

## Summary

When `gates/staged_claim_gate.py` blocks a main-session Stop, its JSON output also carries the blocked reply in
`systemMessage`, so a user in focus mode still sees the reply the hook sent back. A new helper `lib/stop_block.py`
builds that output. Separately, the announced-step check (`gates/announced_step.py`) passes four more gated shapes:
a date or clock gate, a `later <plural noun>` event, a wait on another party's notice or result, and a
Then/Next/After-that sentence that follows a gated one. A bare first-person promise still blocks.

## Phase Status

- [x] Phase 1: Blocked reply shown to the user — contracts folded in (single helper, one caller) (risk: low)
- [x] Phase 2: Gated future steps pass the announced-step check (risk: low)
- [ ] Phase 3: Close pass — /close-branch parallel review, one fix, fix-diff gate, recap (risk: high)

## Plan Deviations

- Phase 1: REPLY_LABEL reads "Its text:", not "Its full text:" (the reply can be cut); session ruling, 2026-11-27.

## Decisions

1. Gated shapes — a sentence passes on a date or clock gate, a `later <plural noun>` event, `act on (its|their|the)
   … (notice|result|report)s?`, or a Then/Next/After-that opening after a gated sentence. Trade-off: own-step
   ordering ("at the end", "before starting", "in my final report") still blocks.
2. Vocabulary — module constants `TIME_GATE`, `LATER_EVENT`, `OTHER_PARTY_RESULT`, `CHAINED_STEP` in
   `gates/announced_step.py`, checked beside `CONDITION`. Trade-off: the sentence loop keeps a `previous_gated` flag.
3. `systemMessage` text — a label line, a blank line, the reply; cut to fit 10,000 characters with a closing cut line.
4. Event — `systemMessage` on Stop blocks only, never SubagentStop.
5. Helper — `lib/stop_block.py` `block_line(reasons, reply, show_reply) -> str | None`.
6. Dates already past — a date gate passes on its words alone; no staleness check.
7. Empty reply — no `systemMessage` key.

## Approaches Considered and Not Taken

- Bare `on`, `at`, `before` or `later` added to `CONDITION`: "I'll work on it" and "I'll look at X" would pass.
- A whole reply passing on a "Your turn:" or "Waiting on:" heading: a bare promise elsewhere in that reply would pass.
- A date-parsing package: a new dependency and more startup time on every Stop.

## Constraints

- Only `gates/staged_claim_gate.py` can block among the Stop and SubagentStop hooks in `claude/.claude/settings.json`:
  `format_changed.py` prints no decision and exits 0; `ledger-hook stop` runs async. `exercised` (read in research,
  02-research.md).
- `settings.json` and every CLAUDE.md stay unedited, except one owner line in `claude/.claude/scripts/CLAUDE.md`.
- The gate fails open: any error exits 0 with a line on stderr (`__main__` block); a crash in one check skips only
  that check (`guarded`). The new code keeps both. `exercised`.
- `stop_hook_active` true returns before any check, so a second block in a row never happens. `exercised`.
- The ticket's three example forms ("once X confirms", "after Nov 29", "when the lane reports") pass today through
  `CONDITION`. `exercised` (probe run on be9a5807d). The before-fails test therefore uses "on Nov 29" and "at :47".
- Baseline time on be9a5807d: bare `python3 -c pass` 8.1 ms, `staged_claim_gate.py` on a blocking payload 43.6 ms
  (median of 21). `exercised`.

## External Contracts

- Claude Code hook output (https://code.claude.com/docs/en/hooks#json-output): `systemMessage` is a warning message
  shown to the user; each output field is capped at 10,000 characters. `declared-only`. The real tool shows it on a
  Stop block only when a live session hits a block; Phase 1's Manual Verification runs that check before the branch
  is done.
- Stop decision control (#stop-decision-control): `{"decision": "block", "reason": ...}`; `reason` is required and is
  what the model reads. Adding `systemMessage` beside them is allowed by the common output fields; the Stop section
  names no exclusion. `declared-only`. If a block were rejected for the extra key, the gate would stop blocking —
  the same Manual check catches it.
- Breaks if violated: a reply over the cap could be dropped whole, so the helper cuts to fit.

## Approach

- `lib/stop_block.py` (new, standard library only):
  ```python
  SYSTEM_MESSAGE_LIMIT = 10_000
  REPLY_LABEL = "A Stop hook sent this reply back to the session. Its text:"
  CUT_LINE = "[The reply was cut here to fit the hook message limit.]"

  def block_line(reasons, reply, show_reply):
      """The JSON line a Stop hook prints to block, or None when no reason holds. With show_reply and a reply, it
      also carries the reply in systemMessage."""

  def shown_reply(reply):
      """REPLY_LABEL, a blank line, then the reply, cut with CUT_LINE so the whole text fits SYSTEM_MESSAGE_LIMIT."""
  ```
  `block_line` drops empty reasons, joins the rest with one space into `reason`, and returns
  `json.dumps({"decision": "block", "reason": ..., "systemMessage": ...})` (no `systemMessage` key when
  `show_reply` is false or the reply is empty).
- `gates/staged_claim_gate.py` `main()` replaces its `found_reasons` print with
  `line = stop_block.block_line(reasons, message, show_reply=is_main_session)` and prints `line` when it is not None.
- `gates/announced_step.py`: four new compiled constants and a `gated(sentence)` function that is true for
  `CONDITION`, `OTHER_ACTOR`, `WORK_RUNS`, `TIME_GATE`, `LATER_EVENT` or `OTHER_PARTY_RESULT`. The loop computes
  `gated` for every sentence (announcement or not) and keeps `previous_gated`; a sentence that matches
  `CHAINED_STEP` passes when `previous_gated` holds, and a chained sentence that passes keeps `previous_gated` true.
  - `TIME_GATE`: `(on|by) <weekday>` (full name), `(on|by) <month> <day>` (full name or 3-letter abbreviation, no
    period, since `SENTENCE_END` splits on it; a 1-2 digit day with an optional `st|nd|rd|th`), `at H:MM`, `at :MM` or `at H[:MM] am/pm`, `tomorrow`,
    `tonight`, `the next time`.
  - `LATER_EVENT`: `later <word ending in s>` excluding `this`, `its`, `is`, `was`, `as`, `perhaps`, `always`,
    `anyways`, `sometimes`, `besides`, `regardless`, `versus`, `afterwards`, `towards`, `yes`, `thus` and `unless`
    ("later merges", "later lanes").
  - `OTHER_PARTY_RESULT`: `act on (its|their|the) (<word> ){0,2}(notice|result|report)s?`.
  - `CHAINED_STEP`: the sentence opens on `then` or `next` (after leading space or list markers `1.`, `2)`, `-`, `*`, `+`);
    `Next step(s)` is a header and does not chain. "After
    that" needs no entry: `CONDITION` already passes `after`.
- The module docstring lists each new pass form under "A sentence is no announcement when it also:", and the chained
  rule as its own paragraph. The `staged_claim_gate.py` docstring adds one sentence: a Stop block also carries the
  reply in `systemMessage` (`stop_block.py`); a SubagentStop block does not.

## Dependencies

- None external. Internal: `lib/message_text.py`, `lib/user_prompts.py` (unchanged).

## Acceptance Criteria

- **Criteria file**: `acceptance-criteria.md` beside the plan

A test covers a criterion by its behavior, never by a marker: it asserts at the public boundary a user or caller
reaches (the gate run as a subprocess on a hook payload), never an internal function. No mocks inside such a test.
One exception: the empty-reply case is tested on `stop_block.block_line` alone, because every Stop check reads the
message text, so an empty reply never blocks through the gate.

## Implementation Plan

## Phase 1: Blocked reply shown to the user

### Overview

Single-slice phase with its contract folded in: the helper and its one caller land together.

### Changes Required:

#### 1. Block output helper

**File**: `claude/.claude/scripts/lib/stop_block.py`
**Changes**: new module per `## Approach`.

#### 2. Gate uses the helper

**File**: `claude/.claude/scripts/gates/staged_claim_gate.py`
**Changes**: `import stop_block`; `main()` prints `stop_block.block_line(reasons, message, show_reply=is_main_session)`
when not None; docstring sentence per `## Approach`.

#### 3. Owner line

**File**: `claude/.claude/scripts/CLAUDE.md`
**Changes**: under `## Owners`, add: "- A Stop hook's block output, with the blocked reply in `systemMessage`:
`lib/stop_block.py` `block_line`."

#### 4. Tests

**File**: `tests/scripts/test_stop_block.py`
**Changes**: new; imports `stop_block` from `toolkit_paths.LIB_DIR`. Cases: no reason gives None; empty reasons
dropped and the rest joined; `show_reply` false gives no `systemMessage` key; a short reply shows as label, blank
line, reply; a 20,000-character reply gives a `systemMessage` of at most 10,000 characters ending on `CUT_LINE`; an empty
reply with `show_reply` true gives no `systemMessage` key.

**File**: `tests/scripts/test_staged_claim_gate.py`
**Changes**: two wiring tests through the gate subprocess: a Stop block (announced-step message "I'll run the suite
next.") whose `systemMessage` contains the whole message; a SubagentStop staged-claim block with no `systemMessage`
key; a Stop block on a 20,000-character reply that holds "I'll run the suite next." whose `systemMessage` is at most
10,000 characters and ends on `CUT_LINE`.

### Success Criteria

A Stop block's output carries the blocked reply in `systemMessage`; a SubagentStop block's output has no
`systemMessage`; a reply over the limit is cut with the cut line and fits 10,000 characters.

#### Automated Verification:

- [ ] **Test-verified**: helper cases pass — `python3 tests/parallel_tests.py test_stop_block.py`
- [ ] **Test-verified**: gate wiring and existing gate tests pass — `python3 tests/parallel_tests.py test_staged_claim_gate.py`
- [ ] **Test-verified**: announced-step tests still pass — `python3 tests/parallel_tests.py test_announced_step.py`
- [ ] **Lint/type-verified**: no new errors — `bash tests/lint.sh claude/.claude/scripts/lib/stop_block.py claude/.claude/scripts/gates/staged_claim_gate.py tests/scripts/test_stop_block.py tests/scripts/test_staged_claim_gate.py`
- [ ] **Agent-run**: median time of `staged_claim_gate.py` beside a bare Python start — `python3 docs/plans/stop-hook-gate-1127/timing/time_hook.py claude/.claude/scripts/gates/staged_claim_gate.py docs/plans/stop-hook-gate-1127/timing/payload_block.json 21` — printed numbers recorded in the Fix 1 change file.

#### Manual Verification:

- [ ] **Manual-verified**: in a live Claude Code session with this branch stowed, end a turn on "I'll run the suite next." with nothing started — confirm the hook warning in the user's pane shows the label line and the full reply, and the turn is sent back once.

---

## Phase 2: Gated future steps pass the announced-step check

### Overview

Add the four pass forms of Decision 1 to the announced-step check; bare first-person promises keep blocking.

### Changes Required:

#### 1. Pass forms

**File**: `claude/.claude/scripts/gates/announced_step.py`
**Changes**: `TIME_GATE`, `LATER_EVENT`, `OTHER_PARTY_RESULT`, `CHAINED_STEP`, `gated(sentence)` and the
`previous_gated` loop state per `## Approach`; docstring per `## Approach`.

#### 2. Tests

**File**: `tests/scripts/test_announced_step.py`
**Changes**: through the gate subprocess (existing `assert_passes` / `assert_blocks`):
- passes: "I'll run the weekly scan on Nov 29.", "I'll recheck at :47.", "I'll run the scan on Monday.",
  "I'll check it tomorrow.", "I'll send later merges to `weekend-toolkit-fixes-v2`.",
  "I'll act on their completion notices.", "Once agent-evals-74 confirms the merge, I'll repoint it. Then I'll push
  the branch.";
- regression passes for the ticket's examples: "I'll repoint it once agent-evals-74 confirms.",
  "I'll run it after Nov 29.", "I'll merge when the lane reports.";
- passes: "The suite is running in the background. Next I'll read its log.";
- still blocks: "I'll run the suite next.", "I'll work on it.", "I'll look at the diff.", "I'll fix that later.",
  "I'll check who holds them before starting any of them.", "- One merge line, which I'll write up at the end.",
  "The tree is clean. Then I'll push the branch.", "The tree is clean. Next I'll push the branch.",
  "I'll list the open items in my final report.".

#### 3. Change files

**Files**: `docs/changes/` (two new files from `python3 /tmp/claude-1000/-home-brandon-dotfiles-stop-hook-keeps-reply/bae07c50-5295-4b22-9573-8fa46faa9d8f/scratchpad/bench-base/bin/build_changes.py new "<title>" --by claude-code/claude-opus-5-5 --root docs/changes`)
**Changes**: the lane session writes both after the timing runs.
- Fix 1, kind `user-rule`: asked 2026-11-27, a paraphrase of the user's ask that a Stop hook never hide a reply
  (never a quote); the doc link https://code.claude.com/docs/en/hooks#json-output; `unmeasured`: hook code, not
  prompt text, so no rule-meter run; the before and after medians beside bare Python.
- Fix 2, kind `fix`: the queue item `stop-hook-blocks-a-reply-whose-next-step-waits-on`; the file::test that fails
  on be9a5807d and passes after (the "on Nov 29" / "at :47" test in `tests/scripts/test_announced_step.py`); a line
  saying own-step ordering ("at the end", "before starting", "in my final report") still blocks; the medians.

### Success Criteria

Each pass sentence above ends the turn with no block; each still-blocks sentence is sent back with the
announced-step reason. "I'll run the weekly scan on Nov 29." and "I'll recheck at :47." block on be9a5807d and pass
after this phase.

#### Automated Verification:

- [ ] **Test-verified**: the new pass and block cases pass — `python3 tests/parallel_tests.py test_announced_step.py`
- [ ] **Test-verified**: gate tests still pass — `python3 tests/parallel_tests.py test_staged_claim_gate.py`
- [ ] **Lint/type-verified**: no new errors — `bash tests/lint.sh claude/.claude/scripts/gates/announced_step.py tests/scripts/test_announced_step.py`
- [ ] **Agent-run**: the 4 real blocked replies in `docs/plans/stop-hook-gate-1127/real_blocks.json` re-run through `announced_step`: reply 4 ("later merges") passes, replies 1-3 still block; the 139 flagged sentences of `flagged.json` re-run with the pass count reported.
- [ ] **Agent-run**: median time re-measured after this phase — `python3 docs/plans/stop-hook-gate-1127/timing/time_hook.py claude/.claude/scripts/gates/staged_claim_gate.py docs/plans/stop-hook-gate-1127/timing/payload_block.json 21` — recorded in both change files.
- [ ] **Agent-run**: both change files pass `python3 /tmp/claude-1000/-home-brandon-dotfiles-stop-hook-keeps-reply/bae07c50-5295-4b22-9573-8fa46faa9d8f/scratchpad/bench-base/bin/build_changes.py --root docs/changes --check` with `AGENT_EVALS_DIR=/tmp/claude-1000/-home-brandon-dotfiles-stop-hook-keeps-reply/bae07c50-5295-4b22-9573-8fa46faa9d8f/scratchpad/bench-base`.

#### Manual Verification:

- [ ] **Manual-verified**: N/A beyond the tests: the check is pure text, driven through the gate subprocess.

---

## Phase 3: Close pass

### Overview

`/close-branch`: scripts first, then four report-only reviewers in parallel on the whole branch diff, one coder for
every finding, a report-only gate on the fix diff, a coder round for its findings, then the recap.

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: full suite green under the memory cap — `bash tests/run.sh`
- [ ] **Agent-run**: every reviewer finding fixed, shown wrong, or put to the orchestrator; fix-diff gate passed; every acceptance criterion mapped to a test; recap delivered.
- [ ] **Agent-run**: `python3 /tmp/claude-1000/-home-brandon-dotfiles-stop-hook-keeps-reply/bae07c50-5295-4b22-9573-8fa46faa9d8f/scratchpad/bench-base/bin/build_changes.py --root docs/changes --check` and `bash claude/.claude/scripts/tools/rule-anchors.sh check` pass.

#### Manual Verification:

- [ ] **Manual-verified**: N/A (closing phase; manual items live in Phase 1).

## Testing Strategy

The helper's case table lives in `test_stop_block.py` only; the gate gets two wiring tests. The pass/block case
table for the announced-step forms lives in `test_announced_step.py` only, run through the gate subprocess.

## References

- ./00-ticket.md, ./02-research.md, ./03-decisions.md, ./real_blocks.json, ./flagged.json
- https://code.claude.com/docs/en/hooks#json-output, #stop-decision-control
