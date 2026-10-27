# /code runs the review loop as a script

Port the benched driver `~/agent-evals/loopscript/loop_driver.py` (sha256 `909ad730…`, 12 benched loops, 0 failed full
checks) into the toolkit. `/code`'s step script runs it where it dispatches the `review-loop` agent today. Port, do not
redesign: keep the driver's steps, prompts, round cap, size bars, closure check and full check as benched.

## Scope

- In: review-first mode with `caller: code`, the path `code_step_review.py` `emit_review_dispatch` takes.
- Out: `/review`, `/fix` and fix-first mode keep the `review-loop` agent. The second-order caller supplement and the
  critical-blocker judgment stay unscripted, as benched.

## Phase Status

- [x] Phase 1: Split code_step.py by concern, no behavior change
- [ ] Phase 2: Port the driver as review/review_loop_script.py
- [ ] Phase 3: code_step launches the script and reads its hand-back
- [ ] Phase 4: The format hook stays off inside the script's sessions

## Phase 1: Split code_step.py by concern, no behavior change

`code_step.py` is 2312 lines; the toolkit script rules forbid a new route or state field in a file over 1000 lines.

- Move the review and asks sections (`# ---------- review ----------` through the asks helpers: `load_review_packet`,
  `carried_findings`, `stop_on_review_status`, `command_after_review`, `present_asks`, `ask_the_user` and their
  helpers) into `code/code_step_review.py`, imported the way `code_step_core.py` and `code_step_hooks.py` are.
- Move any other whole concern needed to bring `code_step.py` under 1000 lines (candidates: plan-impact parsing, the
  handoff block and change lines). Keep each moved function's text unchanged.
- Callers: grep `tests/scripts/` and `claude/.claude/` for each moved name, including tests that patch
  `code_step.<name>`; repoint them.

#### Automated Verification

- `bash tests/run.sh` passes with no test edited except import or patch targets.
- `wc -l claude/.claude/scripts/code/code_step.py` is under 1000; every new module is under 1000.
- `ruff check` passes.

## Phase 2: Port the driver as review/review_loop_script.py

Copy `loop_driver.py` to `claude/.claude/scripts/review/review_loop_script.py`. Adapt only what the toolkit needs:

1. Inputs: `review_loop_script.py <repo> --state-dir <dir> --session <id> --run-id <id> --agent-id <id>
   --prompt-file <path>`. The prompt file is the review prompt `emit_review_dispatch` builds today (header lines
   `mode`, `caller`, `lane`, `plan`, `phase`, optional `structure-pass: skip`, then the handoff block). Read `lane`
   from it. `structure-pass: skip` drops the first-round smell reviewer. Pass the handoff block to each reviewer
   prompt under a `Handoff:` heading. Call logs and raw outputs go under `<state dir>/loop-script/<agent id>/`.
2. Packet: write the result in the hand-back packet grammar `handback.py` reads (`PACKET_KEYS`; statuses from
   `STATUSES`). Map driver `plan-change` to `plan-impact` with `plan_impact` filled; `critical-blocker` with
   `blockers`. `fixed`, `skipped_fp`, `ask` and `nit` entries carry `file_line` parsed with the driver's
   `finding_file`. Validate with `handback.load` before writing; a packet that fails validation exits non-zero
   and names the problems. Never hand-build a second packet grammar.
3. Hand-back rows: on finish, append the same rows the agent path leaves, through the existing writers (never a second
   writer): the code-step run event the log-hook writes for a hand-back (`log_event(..., "handback", ...)` in
   `code_step_core.py`, with `agent_id` = `--agent-id` and the packet as `message`), the hand-back store row
   (`handback.record(session, "handback", ...)`), and the stop row `review_loop_gate.py record_stop` writes
   (`open_dispatches` 0, `ask_rows` from the ask finding rows this run logged). Read the field names from those
   writers and `tests/scripts/fixtures/`; match them exactly, including 704c51b's ask `finding_id` change.
4. Finding rows: keep the driver's `log-review-metrics` and `log-review-finding` calls (`kind=run`, `kind=finding`),
   with `scope` set to the code caller's value the agent uses. Capture each `finding_id=` line `log-review-finding`
   prints for an ask row (`handback.PRINTED_FINDING_ID`) and put it on that ask's packet entry and its stop-row
   `ask_rows` entry.
5. Usage row: append one row per loop run to the agent-usage file `log_agent_usage.py` writes, in its row shape, with
   `agent` `review-loop`, `model` `script`, `tokens` the sum over the run's `claude -p` calls (from each call's JSON
   `usage`, all four token fields), `durationMs` the run's wall time, plus `driver: "script"` and `calls` (count).
   Honor the telemetry switch as `log_agent_usage.py` does.
6. Child sessions: every `claude -p` call runs with `CLAUDE_FORMAT_HOOK_OFF=1` in its environment (Phase 4).
7. Crash path: any uncaught error writes a `critical-blocker` packet naming the error and the call log path, and still
   writes the rows in item 3, so the waiting verb never hangs to the cap.

Tests in `tests/scripts/test_review_loop_script.py`, path from env `REVIEW_LOOP_SCRIPT` defaulting to this tree.
Stub `claude` with a fake on `PATH` that returns canned JSON per role. Cover:
- converged two-round run: packet passes `handback.load`; run event, store row and stop row are written with the
  fields the readers read.
- plan-change ask maps to `plan-impact`; a failing full check after one repair maps to `critical-blocker`.
- an ask's `finding_id` from the logger's printed line reaches the packet and `ask_rows`.
- round-two scope: a coder pass whose diff only reflows quotes and wraps in a file no finding named (simulate the
  format hook) does not put that file in any round-two reviewer's owned files or fix diff, because the format hook
  is off; and with `CLAUDE_FORMAT_HOOK_OFF=1` in the child env, asserted from the fake `claude`'s recorded env.
- a crash mid-run writes a `critical-blocker` packet and the stop row.

#### Automated Verification

- [ ] `python3 -m pytest tests/scripts/test_review_loop_script.py` passes.
- [ ] `ruff check claude/.claude/scripts/review/review_loop_script.py` passes.
- [ ] Human-only: the file is under 1000 lines.

## Phase 3: code_step launches the script and reads its hand-back

- In `emit_review_dispatch`, for `mode: review-first` and `caller: code` only: record the dispatch as today
  (`record_dispatch`, agent type `review-loop`, model `script`), write the prompt file, start
  `review_loop_script.py` detached (`start_new_session=True`, stdout and stderr to a log in its call dir), log the
  launch event with `agent_id` `loop-script-<dispatch id>` exactly as the log-hook logs an Agent launch, then
  `emit("wait", ...)` naming the resume verb with `timed_command`. No Agent call, so the `/code` skill text needs no
  new ACTION.
- `command_after_review` reads the hand-back through the unchanged `wait_for_handback` and `take_handback`. If the
  script process is gone (pid saved in state) with no hand-back row, stop with the call-log path and the
  `review-again` command, not a wait to the cap.
- `review-again` and `abort` kill a running script (saved pid, process group) before they go on.
- Check every caller of the review dispatch and hand-back path: `code_step_hooks.py` (dispatch-hook, log-hook,
  stop-hook), `review_commit_gate.py` `clean` (reads the store row), `review_fix.py packet`
  (`active_code_step` refuses while code-step owns the hand-backs), `review_loop_gate.py`.

Tests in `tests/scripts/test_code_step_review_script.py` (or the existing code_step test files): with a fake script
that writes canned rows, walk review dispatch → wait → hand-back → converged → finish phase; plan-impact; dead script
with no hand-back; `review-again` while running. The walk fails if a path repeats a step or never ends.

#### Automated Verification

- [ ] `python3 -m pytest tests/scripts/test_code_step_review_script.py` passes.
- [ ] `ruff check claude/.claude/scripts/code` passes.

## Phase 4: The format hook stays off inside the script's sessions

- `gates/format_changed.py`: exit 0 at once, on both events, when `CLAUDE_FORMAT_HOOK_OFF` is set. State this in its
  docstring. The main session's turn-end format is unchanged, so the tree is formatted once, after the loop, as with
  the agent today.
- Audit the other Stop hooks (`code_step.py say-hook`, ledger, tuios) for effects inside a `claude -p` child of the
  script; report each as harmless or gate it the same way.

Test in `tests/scripts/test_format_changed.py`: with `CLAUDE_FORMAT_HOOK_OFF=1`, a changed file is not formatted and no
snapshot is written.

#### Automated Verification

- [ ] `python3 -m pytest tests/scripts/test_format_changed.py` passes.

## Done when

- `/code` drives the review loop through `review_loop_script.py`, with tests passing.
- Each coder pass is a fresh `claude -p` session given the parsed fix list.
- A reformat-only diff never reaches a round-two reviewer (Phase 2 test).
- Change file (kind structured, proof `findings/2026-10-26-scripted-review-loop-with-bounded-re-review-vs.md`) and
  two edit watches (review-loop tokens per dispatch, flat or down; review escapes per review run, flat or down) are
  filed by the orchestrator after review.
