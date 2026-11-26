# Code relay and nested fork: a run with no new stop goes on, a code-fork waits for a skill fork it started

Fix two queued /code hand-back defects. Each phase starts with a test that fails on the current tree. Scripts live in
`claude/.claude/scripts/`; tests in `tests/scripts/`, paths from `tests/scripts/toolkit_paths.py`.

## Scope

- In: `code/code_relay.py`, `lib/loop_transcript.py`, `review/open_child_gate.py`, and their tests
  (`tests/scripts/test_code_relay.py`, `tests/scripts/test_open_child_gate.py`, `tests/scripts/test_fork_children.py`
  if its fixtures need the new shape).
- Out: `review/review_loop_scope_guard.py`, `review/review_launch.py` (other lanes own them); every skill and agent
  file (no prompt line changes); `settings.json`; every CLAUDE.md.

## Phase Status

- [x] Phase 1: the relay prints the next step when the run wrote no new stop (risk: low)
- [x] Phase 2: a code-fork cannot hand back while a skill fork it launched in the background still runs (risk: medium)

## Phase 1: the relay prints the next step when the run wrote no new stop

Bug: after a /code fork hand-back that wrote no stop file, `code_relay.py` saw only `stop.prev.md` (the stop
phase_start moved aside) and printed `FALLBACK`: say the Skill result word for word as your whole reply and make no
other tool call. A main session running a skill that invoked /code then had to judge the message stale and go on
against the relay's instruction.

1. Replace `FALLBACK` with `NO_STOP_RULE`: relay the Skill result in place of a stop. When the Skill result has a
   `To go on:` line, it waits on the user: say it word for word as the whole reply and make no other tool call.
   Otherwise the run is finished: when a skill the main session runs invoked this one, go on with that skill's next
   step; otherwise say the Skill result word for word and make no other tool call.
2. Every no-new-stop exit uses it: no stop file, only a moved-aside `stop.prev.md` that is not a bounced stop, and a
   stop already relayed. Exit code (1) and stream (stderr) stay as they are, so callers (the /code, /review and /fix
   skill descriptions: "do what it prints") read the new text unchanged.
3. Update the module docstring to name the new rule.

4. Tests in `tests/scripts/test_code_relay.py`: a run folder with only `stop.prev.md` (no `stop.md`, not bounced)
   exits 1 and prints the go-on-with-the-next-step rule, not `Say the Skill result word for word as your whole reply`
   (fails on the current tree); the existing tests that assert the old FALLBACK text read the new rule.

#### Automated Verification

- [ ] **Relay tests**: `python3 tests/parallel_tests.py test_code_relay.py`

## Phase 2: a code-fork cannot hand back while a skill fork it launched in the background still runs

Bug: a code-fork that invokes the `review`, `code` or `fix` Skill starts a forked run in the background (the Skill
result's `toolUseResult` holds `status: "forked"`, `background: true` and the child's `agentId`; the child's
transcript is the sibling `agent-<agentId>.jsonl`; its task notification carries the Skill call's tool_use_id and the
agentId as task id). `open_child_gate` counts only `Agent` launches, so the code-fork hands back at once with no loop
status and the caller waits on a grandchild it cannot address.

1. `lib/loop_transcript.py` `LoopTranscript`: record the tool_use_ids of `Skill` calls; when a record's
   `toolUseResult` is a dict with `status == "forked"`, `background` true and an `agentId`, map the Skill call's
   tool_use_id to that agentId. Add `open_skill_forks()`: the agent ids of those forked runs with no task notification
   (by tool_use_id or task id), no agent message, and whose agent has not ended on an API error.
2. `review/open_child_gate.py` `live_children`: add each agent id from `open_skill_forks()` whose sibling transcript
   does not show it finished (`loop_transcript.agent_finished`). The existing once-per-child deny and its reason
   (wait with `code_wait.py agent <agentId>`) apply unchanged. `fork_children.py` reads `live_children`, so its
   TaskStop guard and cancel listing cover the forked run too.
3. A foreground Skill (the result text `Launching skill: ...`, no `status: "forked"`) is never counted.

4. Tests in `tests/scripts/test_open_child_gate.py`, with a fixture of the real code-fork shape (Skill tool_use;
   tool_result `Skill "review" launched (forked execution, running in the background)...`; `toolUseResult`
   `{"success": true, "commandName": "review", "status": "forked", "background": true, "agentId": ...}`): a code-fork
   hand-back with that forked run open and an unfinished sibling transcript is denied and names the agent id (fails on
   the current tree); after a task notification for it, it passes; with the sibling meta `finished: true`, it passes;
   a foreground `Launching skill: review` result passes.

#### Automated Verification

- [ ] **Gate tests**: `python3 tests/parallel_tests.py test_open_child_gate.py test_fork_children.py`
- [ ] **Lint**: `bash tests/lint.sh claude/.claude/scripts/code/code_relay.py claude/.claude/scripts/lib/loop_transcript.py claude/.claude/scripts/review/open_child_gate.py`

## Plan Deviations

- ruling, 2026-11-26, the orchestrating session (agent-evals lane): a /code fork that dies with no stop and no "To go on:" line matches NO_STOP_RULE's finished branch; plan step 1 dictates the wording, so it stays and the risk is recorded. The /code SKILL.md description gains no third outcome (skill files out of scope; a skill line needs rule-meter runs).
- ruling, 2026-11-26, the orchestrating session (agent-evals lane), branch review: the gate keeps reading the Skill result's agentId, not the subagent meta's parentAgentId; real meta files show only their finish-time write, so a meta present at launch is unproven. The relay keeps picking the newest stop file; the code-fork deny reason now tells the fork to write its stop again after the wait.
