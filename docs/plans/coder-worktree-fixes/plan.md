# Coder and worktree fixes

Fix queue items `forked-worktree-workspace-closes-about-a-minute`,
`review-coder-deletes-untracked-files-it-did-not` and `review-class-closure-sweeps-readers-without`.
`worktree-rule-reads-as-an-order-to-create` and the no-delete half of the untracked-file item were cut, see Plan
Deviations. Each phase starts with a test that fails on the current tree.

## Scope

- In: `scripts/.local/bin/herdr-worktree`, a new `scripts/.local/bin/herdr-worktree-watch`, a new
  `scripts/.local/bin/detach` (and the `bookmark` and `research` launchers that use it),
  `claude/.claude/skills/coder-core/SKILL.md`, `claude/.claude/scripts/review/review_loop_closure.py`
  (`CLOSURE_RULES`, the closure prompt and the recovery parser `closure_from_open_list`),
  `claude/.claude/scripts/review/review_loop_script.py` (`class_closure_pass`),
  `claude/.claude/scripts/review/review_loop_packet.py` (`packet_message`, `EMPTY_OUTCOME`),
  `claude/.claude/scripts/review/handback.py` (the `left_alone` field), `claude/.claude/scripts/review/review_loop_findings.py` (`reply_with_one_retry`'s `problem` check),
  `claude/.claude/scripts/lib/script_utils.py` (`is_nonblank_string_list`),
  `claude/.claude/scripts/review/review_loop_prompt_file.py` (`read_findings`), and their tests in `tests/scripts/`. `claude/.claude/orchestration.md` (the worktree
  bullet) was in scope and is not shipped: reverted, see Plan Deviations.
- Out: `review_loop_coder.py` (its untracked-file restore already exists and stays as is), `review_fix.py`,
  `review_fix_asks.py`, `skills/review/`, `skills/fix/`, `review-fork-run.md`, lint, format, gate-env and
  removed-change code, `settings.json`, any `~/agent-evals/` file.

## Phase Status

- [x] Phase 1: herdr-worktree watches the forked workspace and names the recovery steps (risk: medium)
- [x] Phase 2: coder scripts go to the scratchpad (risk: low). The no-delete-untracked-file half was reverted, see Plan Deviations
- [x] Phase 3: class closure checks what each member reads the value for (risk: low)

## Phase 1: herdr-worktree watches the forked workspace and names the recovery steps

The cause of the closing workspace is unknown. The script cannot keep it open, so it makes a close visible and names
the recovery. It never reopens the workspace by itself: the user may have closed it on purpose.

1. New bash script `scripts/.local/bin/herdr-worktree-watch <workspace id> <worktree> <main checkout> <claude pane>`
   (`set -euo pipefail`, header usage comment like `herdr-worktree`).
   - Poll `herdr-api pane get <claude pane>` once a second for a non-empty
     `.result.pane.agent_session.value`, bounded by `HERDR_WORKTREE_WATCH_SECONDS` (default 120); empty when the pane
     is already gone. Then sleep the time left of that wait.
   - `herdr-api workspace get <workspace id>`. Exit 0 succeeds: log one line `workspace <id> still open` and exit 0.
   - On a non-zero exit whose stderr holds `.error.code == "workspace_not_found"`, the workspace is gone. Any other
     failure logs `could not check workspace <id>: <error>` and exits 1. Log the recovery steps with literal values:
     `herdr worktree open --cwd <main checkout> --path <worktree> --focus` (without `--cwd`, open fails with
     `linked_worktree_source`), then `herdr-dev <worktree> <new workspace id> <fork session id> '<resume prompt>'`, where
     the new workspace id is the one `open` prints. When the session id is empty, the log says so and gives
     `claude --resume` in the worktree in place of the herdr-dev line. Under `TUIOS_SOCKET` step 1 is
     `herdr-api workspace create --cwd <worktree> --label <worktree folder name> --focus`, because tuios answers no
     `worktree.create`.
   - Show the same text to the user: `herdr notification show "herdr-worktree: workspace closed" --body <one line
     that names the worktree and the log path> --sound request`. Skip the notification under `TUIOS_SOCKET` (tuios
     has no notification command); the log still gets the steps.
   - The log is `herdr-worktree-watch.log` in the worktree's git dir
     (`git -C <worktree> rev-parse --path-format=absolute --git-path herdr-worktree-watch.log`).
2. `herdr-worktree`: once the fork's pane shows the claude agent (the `exit 0` inside the wait loop), start the
   watcher detached (`setsid "$bin_dir/herdr-worktree-watch" ... >/dev/null 2>&1 &` with stdin from `/dev/null`;
   `perl -MPOSIX -e 'POSIX::setsid(); exec @ARGV' --` when `setsid` is missing) and
   print one stderr line: `herdr-worktree: watching workspace <ws> for <N>s; recovery steps go to <log path> if it
   closes`. Then exit 0. A run without `--fork` starts no watcher.
3. `herdr-worktree` header: add a paragraph that names the recovery line (and the `claude --resume` fallback), so `--help` shows them.

#### Automated Verification

- New tests in `tests/scripts/test_herdr_worktree_watch.py` (script path from one env var, stubs from `stubs.py`
  like `test_herdr_worktree.py`, `HERDR_WORKTREE_WATCH_SECONDS=0`): a workspace that `workspace get` still finds logs
  `still open` and calls no notification; a gone workspace writes one recovery line with the literal worktree, main
  checkout and session id to the log and calls `herdr notification show`; a gone workspace with an empty session id
  logs the `claude --resume` line; under `TUIOS_SOCKET` no notification is called and the log still holds the steps; a
  session id that appears after the first poll is picked up, and a session id that never appears is polled once a
  second for the whole wait.
- New tests in `tests/scripts/test_herdr_worktree.py`: a `--fork` run whose pane shows the claude agent starts
  `herdr-worktree-watch` with the workspace id, worktree, main checkout and pane id (a stub records its args); a run
  without `--fork` starts no watcher; `--help` output names `herdr worktree open --cwd`.
- `python3 tests/parallel_tests.py test_herdr_worktree.py test_herdr_worktree_watch.py` passes;
  `bash -n` on both scripts passes.

## Phase 2: coder scripts go to the scratchpad

Prompt edits only.

1. `skills/coder-core/SKILL.md` line 30: replace `Write a script under \`scratch/scripts/\` and run it.` with
   `Write a script in your scratchpad directory, never in the repo tree, and run it.`
2. Guidance tests in `tests/scripts/test_guidance_rules.py`: coder-core names the scratchpad for scripts and no longer
   names `scratch/scripts/`.
3. No opencode port: opencode loads `~/.claude/skills/` as is.

#### Automated Verification

- The new guidance tests fail on the current tree and pass after:
  `python3 tests/parallel_tests.py test_guidance_rules.py`.

## Phase 3: class closure checks what each member reads the value for

1. `review_loop_closure.py` `CLOSURE_RULES`: add, after the two shapes: before you call a member open, say what it
   reads the value for, next to what the fixed line reads it for. A member that reads the value for a different
   purpose than the fixed line is not in the class: leave it, and list it under `left_alone` with that purpose. Never
   list it as open.
2. The closure prompt's reply line: the `left_alone` list names each member left alone and why, next to the enumeration.
3. Test in `tests/scripts/` (the existing closure test file, or `test_review_loop_closure.py` when none exists): the
   prompt that `closure_check` sends holds the purpose check and asks for the members left alone in the `left_alone` list.

#### Automated Verification

- The new test fails on the current tree and passes after, through `python3 tests/parallel_tests.py <file>`;
  `bash tests/lint.sh claude/.claude/scripts/review/review_loop_closure.py` passes.

## Plan Deviations

- Phase 1 step 2: the watcher starts under `setsid`, with perl `POSIX::setsid()` as the fallback where `setsid` is missing (macOS; perl ships with it).
  The perl fallback forks first when the process is a process-group leader (setsid fails for a leader) and exits
  non-zero when fork, setsid or exec fails.
  The caller's process group can be torn down, so the watcher needs its own session.
- Phase 1 step 1: the user directed that the watcher poll `pane get` once a second for the session id, bounded by
  `HERDR_WORKTREE_WATCH_SECONDS`, and sleep the rest, in place of one read at start.
- Phase 1 step 2: `bookmark` and `research` get the same perl `POSIX::setsid()` fallback so they detach on macOS.
  All three launchers call one stowed command, `scripts/.local/bin/detach`, in place of copying the fallback.
- Phase 1: the dependency-install and push failure messages in `herdr-worktree` quote the folder, branch and
  install command with `printf %q`, so the printed hints paste into a shell as written.
- Phase 3 step 1: the rule reads "say what it reads the value for, next to what the fixed line reads it for" (review
  round 1), so `the value` has a referent. Step 1 above quotes the shipped wording.
- Phase 3 step 2: the closure reply JSON carries the members left alone in a `left_alone` list, not in the receipt
  prose, because `review_loop_script.py` rebuilds the receipt from open and held members when any member is open and
  would drop that prose. `class_closure_pass` stores the list in its own `left_alone` packet field, which the
  hand-back renders as its own line, so the hand-back names every member left alone on every path, including a
  missing receipt. This
  widens scope to `review_loop_script.py`, `review_loop_packet.py`, `handback.py` and their tests.
- The former Phase 2 step 2 (the no-delete-untracked-file sentence) and the former Phase 4 (the orchestration.md
  worktree bullet, removed from this plan): reverted before merge on the orchestrator's ruling (agent-evals-5e, 2026-11-10). The
  rule meter's off arm already held 8 of 8 for both lines (CD01, WT01), so they cost tokens and change nothing.
  The phase 2 scratchpad line ships.
- Phase 1 step 2: the herdr-dev recovery step passes a fixed resume prompt ("Go on with the work in this worktree;
  your brief is already in context.") in place of `"<prompt>"`, so the fork does not restart its brief. The
  orchestrator (agent-evals-5e, 2026-11-10) ruled it; AC2 still holds.
- Phase 1 step 1: with a session id, the watcher logs one paste-ready line,
  `ws=$(<reopen> | jq -r '.result.workspace.workspace_id // empty') && [ -n "$ws" ] && herdr-dev <worktree> "$ws" <session>
  '<resume prompt>'`, in place of two steps with a `<new workspace id>` placeholder, so every value is literal
  (branch review 4 ask). Adopted by the coder-worktree-fixes lane session, 2026-11-11, under the verify-branch rule
  that an ask cutting no AC takes its proposed change; not a user sign-off. With no session id, step 1 is the reopen and step 2 is `claude --resume`, as before.
- Phase 1 step 1, tuios: tuios's `workspace get` reply for a missing workspace is unchecked (tuios is not on this
  machine). An unknown reply logs "could not check workspace" and exits 1, so it fails safe. The orchestrator
  (agent-evals-5e, 2026-11-10) ruled it a manual smoke check; not a user sign-off.
- Phase 3: the user ruled "ship" on the class-closure edit (44bab1ba), 2026-11-10, in session agent-evals-5e.
- Phase 3 step 2: the orchestrator (agent-evals-5e, 2026-11-10) ruled that the members left alone get their own
  packet field, which the hand-back shows even when the closure receipt is missing. This is not a user sign-off.
- AC5 and AC8 cut, AC7 reworded from "receipt" to "hand-back": user sign-off, Brandon Corey, 2026-11-10, written
  by the user's own command.

- 2026-11-11: Adopt plan change. Ruled by the session, not the user at 2026-11-11 00:29.

  The ruling: Adopted by the coder-worktree-fixes lane session (session ruling, not the user) on 2026-11-11 under the verify-branch rule; AC2 unchanged; Plan Deviations bullet names this

  The disagreement:
  docs/plans/coder-worktree-fixes/plan.md:43-46 [plan-drift] — PLAN-IMPACT: Phase 1's step text still describes two logged steps with a `<new workspace id>` placeholder. The code now logs one line that captures the id. The new Plan Deviations bullet (lines 133-136) records the change but cites "branch review 4 ask" as its authority. No orchestrator or user ruling is named, while the sibling bullets each name who ruled and when. Question: did the orchestrator or the user approve the one-line form? If so, who and when? Change: add that name and date to the deviation bullet. acceptance_criteria: none (AC2's literal recovery steps hold either way).
