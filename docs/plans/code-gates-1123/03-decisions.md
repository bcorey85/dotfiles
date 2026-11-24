# Design Decisions — code-gates-1123

> Research: ./02-research.md
> Status: 7/7 resolved

## Queue

- [x] D1. Item 1: where the hand-back review check runs — from backend-architect
- [x] D2. Item 1: what proves the review ran for this fork — from backend-architect
- [x] D3. Item 1: the recorded reason that lets a fork skip review — from backend-architect
- [x] D4. Item 2: how the announced-step gate tells started work from an announcement — from backend-architect
- [x] D5. Item 3: what inline-interpreter deny comes back under the auto pilot — from backend-architect (item left the plan)
- [x] D6. Item 4: which reader programs count as cutting a check's output — from backend-architect
- [x] D7. Item 2: where the turn starts for the launch check — from backend-architect (DESIGN GAP)

## Resolved

### 1. Item 1: where the check runs

- **Choice:** a new module `lib/fork_review.py`, called from `gates/staged_claim_gate.py` on the SubagentStop event for a `code-fork` whose task starts with `/code`, the way `announced_step` is called on Stop, and from the code-fork branch of `code/coder_gate.py` `run_hook` on PreToolUse SubagentHandback, which denies the hand-back of a fork that coded a phase and ran no review (shipped in Phase 4; recorded in spec.md `## Decisions` item 1).
- **Reasoning:** staged_claim_gate is already registered on SubagentStop, so no settings.json edit is needed (settings.json is outside the lane's go-ahead). About 92% of code-fork endings are a final text reply, which only SubagentStop sees. The incident fork ended that way. Ruled by the lane session, 2026-11-23.
- **Alternatives rejected:** a new settings.json hook (needs the user's manual edit; the fix would not ship until then); a main-side check in code_relay.py (fires after the fork is gone, so the review still never runs); review/open_child_gate.py (another lane's folder).
- **Trade-off accepted:** a fork whose transcript cannot be read ends unjudged (fail open). A fork that ends through a SubagentHandback call is covered by the deny in `coder_gate.py`; the SubagentStop field names come from no captured event. Ruled by the lane session, 2026-11-24 (spec.md `## Decisions` item 1).

### 2. Item 1: freshness signal

- **Choice:** read the fork's own transcript. After its first coder dispatch, the fork must have run `code_review_start.py` and a `code_wait.py review`, or written a `stop.md`. Read through `lib/loop_transcript.py` and `script_utils` helpers.
- **Reasoning:** the run folder holds leftovers from earlier runs in the same repo, so a packet file there passes on stale state. The transcript is this fork's own record. Ruled by the lane session, 2026-11-23.
- **Alternatives rejected:** a packet file in the run folder (passes on a stale packet from an earlier run); run-folder mtimes against the dispatch (races with other runs in the repo).
- **Trade-off accepted:** a fork with no coder dispatch (a /code run that stopped before coding) is never blocked.

### 3. Item 1: the recorded reason

- **Choice:** a `stop.md` the fork wrote after its coder dispatch counts as the recorded reason. The SKILL.md STOP rule already makes every STOP write stop.md.
- **Reasoning:** it reuses an existing owner (`lib/stop_file_names.py`) and invents no field. The AC allows "a recorded reason the step allows"; stop.md is the record the step already writes, so the AC is met, not narrowed. Ruled by the lane session, 2026-11-23.
- **Alternatives rejected:** a new skip-reason field in a run-folder file (new state no step writes today).
- **Trade-off accepted:** a fork can dodge review by writing a stop.md; the main session reads stop.md and sees the stop.

### 4. Item 2: the fix

- **Choice:** the subjectless progress forms (`working on it`, `on it now`, `starting ... now`) pass only when the final turn launched background work after the latest user prompt: a Bash call with `run_in_background` true (bool or string) or an Agent call, which counts unless `run_in_background` is explicitly false (the Agent tool runs in the background by default). The flag reads live in stdlib-only `lib/tool_call_flags.py`, and the turn reader `turn_launched_background` lives in `lib/user_prompts.py`. First-person future forms ("I'll ...") still block. The transcript read tolerates a torn last line, and the gate's crash no longer drops the staged-claim reason.
- **Reasoning:** the incident sentence was "a new agent is working on it", a subjectless form, after a turn that started a background shell and an agent. Exempting all open background work would pass 6 of 8 real, correct blocks. Ruled by the lane session, 2026-11-23.
- **Phase 2 ruling:** an Agent call counts as a background launch unless `run_in_background` is explicitly false. By the orchestrating /code session, 2026-11-24.
- **Alternatives rejected:** exempt any open background work in the session (lets true announcements through); drop the subjectless forms (lets "working on it" through on a turn that started nothing).
- **Trade-off accepted:** the gate reads the transcript when a subjectless form matches; parse runs only after the regex hit.

### 5. Item 3: left the plan

- **Choice:** item 3 (inline-python-heredoc-that-rewrites-an-untracked) leaves this plan unfixed and goes back to the queue. Its Done-when is not met by this branch and is not reported as met.
- **Reasoning:** ruled by agent-evals-c3-owner (orchestrating session), 2026-11-23. The auto-mode gate pilot is a live experiment, read on 2026-11-29 and 2026-12-06, and a new deny would add a second variable. The queue item waits on the pilot reading.
- **Alternatives rejected:** a narrow deny under the pilot for subagent stdin code that writes a file (changes the experiment mid-run); deny all subagent stdin code under the pilot (same, and wider).
- **Trade-off accepted:** inline write heredocs keep passing under auto mode until the pilot is read.

### 6. Item 4: readers

- **Choice:** add `rg` to `OUTPUT_FILTER_START`, and reword `CUT_DENY_TEXT` to name it.
- **Reasoning:** rg is the reader a session hit (86 pipes after a check in the survey). sed, awk and the rest were never reported. Ruled by the lane session, 2026-11-23.
- **Alternatives rejected:** add sed, awk, cut too (no session hit them; size rule).
- **Trade-off accepted:** a check piped into sed or awk still reads as seen in full.

### 7. Item 2: the turn boundary

- **Choice:** the turn starts at the latest record that opens a turn: a typed prompt, a `!` shell echo, a task notification or a peer message (new `lib/user_prompts.py` `starts_turn`). The launch must come after that record.
- **Reasoning:** the latest typed prompt (`prompt_text`) fell hours before the incident block in a session driven by notifications, which makes the exemption close to the session-wide one D4 rejected. In the incident the turn opened at 03:19:26Z on a `!` echo, and both launches fall inside it. Ruled by the lane session, 2026-11-23, on the architect's DESIGN GAP.
- **Alternatives rejected:** the latest typed prompt (passes a progress line hours after the launch).
- **Trade-off accepted:** a progress line in a notification turn, with the launch in an earlier turn, blocks.

### 8. Damage-path questions from the criteria draft

- **Choice:** the lane session ruled these on 2026-11-24. `plan_check.py owner` names the owner as `session`, a session-written queue item.
  - A transcript or meta file that is missing, unreadable or torn lets the fork end: fail open, the gates' standing mode. A torn line is skipped, and the rest is read.
  - A `stop.md` counts whatever it says. The main session reads its text through code_relay.
  - A second stop after the one send-back passes (`stop_hook_active`), to keep the gate from looping.
  - A review after the first coder dispatch counts for later dispatches too. Every legal end of a multi-phase run writes `stop.md`.
  - When the announced-step transcript read fails, a subjectless progress line blocks, as it does today.
  - sed, awk and cut stay out of scope (block 6).
- **Reasoning:** each choice keeps a gate's current fail mode, or follows from blocks 2, 3 and 6. None of them cuts an AC.
- **Alternatives rejected:**
  - Fail closed on an unreadable transcript: a torn live file would trap a fork.
  - Require a reason line in `stop.md`: a new format with no reader.
  - Require a review after each coder dispatch: blocks multi-phase runs that review per phase and stop at the end.
- **Trade-off accepted:** a fork that ignores the one send-back ends unreviewed.
- The AC1 coverage gap for forks that end through a SubagentHandback call was sent to agent-evals-c3-owner for a ruling.

### 9. Plan review round 1 rulings

- **Choice:** the lane session ruled these on 2026-11-24.
  - **BLOCKER, real-block input.** The Phase 2 sweep reads every past block of this gate, found by searching `~/.claude/projects` transcripts for the `announced_step.REASON` text. It reports "N of M still block". Each block that now passes is labelled by hand as the incident shape (progress form, launch in the same turn) or a gate gap. The "8 real blocks" wording is dropped.
  - **GAP, per-phase anchor.** The fork transcript is split into segments at each `phase_start.py` call. A transcript with no such call is one segment. A segment that holds a coder dispatch needs one of these after its first coder dispatch: a `code_review_start.py` call followed by a `code_wait.py review`, or a `stop.md` write. The tick coder dispatched after a converged review falls after the review, so it never needs a second review.
  - **GAP, hand-back path.** The same check also runs from the code-fork branch of `code/coder_gate.py hook`, which is already registered on PreToolUse SubagentHandback. It denies the hand-back with the same reason. No settings.json edit is needed. This closes AC3 for the ~8% of forks that end through a hand-back, and replaces the block 1 trade-off and the coverage gap sent to agent-evals-c3-owner. Writing `stop.md` always clears the deny, so the fork cannot be trapped.
  - **NIT, agent type.** Read the coder type through `script_utils.CODERS`. Drop `CODER_AGENT_TYPE`, and leave the coder_gate `"coder"` literals as they are.
  - **NIT, phase size.** The name owner and `script_call_arguments` become their own phase.
  - **NIT, copied lib list.** Add `test_telemetry_switch.py` and `test_import_guard.py` to the Test-verified list of the phase that changes `CODER_GATE_LIB_MODULES`.
  - **NIT, AC6.** Add a test for a stale `stop.md` write before the coder dispatch, and one for a stale run folder holding `review.out` and `stop.md`.
  - **NIT, count.** Correct the count to 1337 of 1754 code-fork transcripts.
  - **Dropped:** the scope-box and `echo` pin NITs (template form; already recorded).
- **Reasoning:** each ruling closes the finding with existing hooks and owners.
- **Alternatives rejected:**
  - Anchor on the last coder dispatch: sends back every correct run, because of the tick coder.
  - Leave the hand-back path unjudged: narrows AC3.
- **Trade-off accepted:** a fork whose transcript cannot be read still ends unjudged (fail open).

## Direction & Constraints

- code_step.py no longer exists (removed 7b347d962); /code runs as prompt steps in skills/code/SKILL.md.
- Item 2's ticket premise is off: "is running" already passes through WORK_RUNS. The test must use the incident sentence "a new agent is working on it" to fail before the fix; it also keeps the AC's "is running" case.
- Item 3's "2026-10-27 fix" (shell_write_gate.py) was deleted at the user's request on 2026-11-21 (d1b7a463d). Restoring it is ruled out. inline_interpreter_hint.py already denies `python3 - <<EOF` by text; the incident passed through the auto-mode pilot (`pilot_passes`), which logs and allows.
- No settings.json edits. No scripts/review edits. SKILL.md hunks stay small.
- Earlier rulings: 2026-11-23, agent-evals-c3-owner (orchestrating session) ruled the lane triage: five of nine briefed items left this plan (four dropped, the hillclimb pricing script returned to the queue). 2026-11-23, agent-evals-c3-owner: refactor/readability-worst-ten also edits skills/code/SKILL.md and scripts/code/gate_commands.py; keep SKILL.md hunks small and merge origin/master before the push.
