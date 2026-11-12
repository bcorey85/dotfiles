# Review loop batch 2: no stale launch inputs, whole carried findings, leave-it outcome text, split-commit credit

Fix four queue item groups from /review and /fix runs. Each phase starts with a test that fails on the current tree.
Scripts live in `claude/.claude/scripts/`; tests in `tests/scripts/`, paths from `tests/scripts/toolkit_paths.py`.

## Scope

- In: `review/review_launch.py`, `review/review_fix_asks.py`, `review/handback.py` (`carried_findings` only),
  `review/review_fix.py` (one `one_line` limit only; it is 1000 lines, so no new verb, route or state field),
  `lib/reviewed_tree.py`, and the tests of each.
- Out: every skill, agent and CLAUDE.md file (no prompt edits in this batch); `review/review_loop_script.py`;
  `review/review_commit_gate.py` (it reads `reviewed_tree.is_reviewed` and needs no change); the files the parallel
  lane `fix/verify-misc-batch` owns.

## Phase Status

- [x] Phase 1: launch consumes its run-folder inputs and stops older loops of the same repo (risk: medium)
- [x] Phase 2: asks-done outcome error says which outcome a leave-it option takes (risk: low)
- [x] Phase 3: carried findings and plan impact reach the adopt handoff whole (risk: low)
- [x] Phase 4: a split commit of a reviewed tree keeps review credit (risk: medium)

## Phase 1: launch consumes its run-folder inputs and stops older loops of the same repo

Bug: a failed Write of `<run folder>/review-handoff.txt` or `<run folder>/fix-findings.md` left the previous run's file
in place, so `review_launch.py launch` started a fix loop on stale findings. A second launch left the first loop
running, and both edited the tree.

1. `review_launch.command_launch`: after it copies the `--fix` and `--handoff` contents into `loop_dir`, delete each
   original when its parent folder is the code-phase run folder (name from its owner, `code_wait.PHASE_DIR_NAME` or
   `fork_write_scope.RUN_FOLDER_NAME`; import, never retype). Never delete the asks findings file
   (`review_fix_names.ASK_FINDINGS_NAME` under `review-fix/`) or a file outside the run folder.
2. (Dropped; see Plan Deviations.)
3. Before it starts the new loop, stop each live loop of the same repo: read `state_dir/loops/*/launch.json` and
   `loop.pid` (names from their owners), match the repo, confirm the pid's command line names that loop's agent id
   (`ps -o command= -p <pid>`), and SIGTERM its process group. Print one line per loop stopped. A pid that is gone or
   names another command is skipped silently; a `ps` or kill error is printed on stderr and launch goes on.

#### Automated Verification

- New tests in `tests/scripts/test_review_launch.py` (or the existing launch test file): a launch with run-folder
  `--fix` and `--handoff` files deletes both and keeps `review-stop.md`; a launch with files outside the run folder
  and with the asks findings file keeps them; a second launch of the same repo stops the first loop's live process
  group; a loop of another repo is left running.
- `python3 tests/parallel_tests.py <launch test file>` passes.

## Phase 2: asks-done outcome error says which outcome a leave-it option takes

Bug: a user picked an ask's "leave it" option, and the fork logged `accepted`, which applies the proposed change.

1. `review_fix_asks.read_outcomes`: the unknown-outcome error names each outcome's effect: `accepted` applies the ask's
   proposed change; `rejected` leaves the code as it is (the outcome for a "leave it" or "accept the gap" option);
   `modified:<change>` applies another change.

#### Automated Verification

- A test that an unknown outcome word exits non-zero and its error names the leave-it rule for `rejected`.

## Phase 3: carried findings and plan impact reach the adopt handoff whole

Bug: `decide --adopt` wrote the adopt handoff with each carried finding cut at 800 characters.

1. `handback.carried_findings`: keep each finding whole on one line (`one_line(text, None)`).
2. `review_fix.py` plan impact line: `one_line(impact['text'], None)`.

#### Automated Verification

- A test that a carried finding over 800 characters appears whole in the adopt handoff `redispatch_lines` writes.

## Phase 4: a split commit of a reviewed tree keeps review credit

Bug: `reviewed_tree` fingerprints the diff against HEAD, so after the first of two commits that split a reviewed tree,
the second commit's fingerprint no longer matches and the commit gate asks for a new review.

1. `record_reviewed` also stores, per session and repo top, the HEAD at record time and the tree fingerprint, in a
   separate file beside the record, written with `write_text_atomically`. `read_reviewed`'s keys stay repo tops.
2. `is_reviewed`: when the current check fails and the stored base is an ancestor of HEAD
   (`git merge-base --is-ancestor`), compute `tree_fingerprint` against the stored base (same notes-path exclusions)
   and compare it to the stored fingerprint. An unborn repo or a missing base file falls back to today's answer.
3. The only writer stays `handback.record_clean_review` → `record_reviewed`.

#### Automated Verification

- Tests in `tests/scripts/test_reviewed_tree.py`: record a reviewed two-file change, commit one file, and the rest is
  still reviewed; an edit after the first commit is not reviewed; a HEAD that is not a descendant of the base is not
  reviewed.

## Plan Deviations

- The asks-done usage text in `review_fix.py` now builds its outcome list and the accepted/rejected meanings from the `review_asks` constants, and the `modified:` examples in `review_fix.py` and `review_fix_asks.py` use `MODIFIED`.
- Pending sign-off (no user sign-off yet, change left unapplied): asks-done would print one line per ask giving its outcome and effect (built from ACCEPT_MEANS and REJECT_MEANS), because a valid word like accepted for a leave-it pick never reaches the new unknown-outcome error; this changes Phase 2's bug statement. Raised by review, 2026-11-11. Ruled not applied by the lane session (claude-code/claude-opus-5-5), 2026-11-11: in the reported run the fork's first call with the option letter failed, and that error is where the fork chose `accepted`, so the error text covers the sighting; the queue item's done-when asks no per-ask echo.
- The adopt handoff's `Ruling:` text in `review_fix.py` is kept whole too (`one_line(ruling, None)`), as are the carried loop note and plan impact lines, so long text reaches the next review uncut (session ruling on a review ask, 2026-11-11; no criterion changed).
- `record_base` stores the base only when a stored hand-back tree hash re-matches the fingerprint against the HEAD read at record time; otherwise nothing is stored (fail closed), so a delayed ruling after a commit keeps no split-commit credit (session ruling on a review ask, 2026-11-11; no criterion changed).
- Ticket #11 (decide-adopt, Plan Deviations line written to the plan) is cut by the lane session (claude-code/claude-opus-5-5) under the queue triage rules, 2026-11-11: with no `--plan`, decide already prints `NO_PLAN_LINE` telling the session to add the lines under `## Plan Deviations`, and the adopt handoff names no plan, so the sighting was a model slip.
- Ticket #6 and #7 (fix findings freshness, clearing on stop) are met by launch deleting the run-folder findings file it read (Phase 1): any findings file present at launch was written after the previous launch, and no old file outlives a run. Ruled by the lane session, 2026-11-11.
- Files touched outside Scope: `lib/script_utils.py` gains `head_commit`, and its callers `code/phase_start.py`, `review/review_loop_plan.py`, `review/review_loop_coder.py`, `review/review_loop_script.py` use it in place of their own copies (toolkit rule: move a duplicated helper into the shared module); `review/reviewer_dispatch.py` gains `live_loops`, shared by `waiting_launch_lines` and `review_launch.stop_earlier_loops`; `lib/process_group.py` is new. No route or behavior change in those callers.
- AC1 reworded by the lane session (claude-code/claude-opus-5-5), 2026-11-11, on a branch-review ask: launch no longer deletes `review-stop.md`, because `code_relay` would then relay an older `stop.md`; the relay's `relayed` stamp already blocks a stale review stop.
- Ticket #2 is met by AC2: a relaunch stops the loop launched by mistake. Ticket #9 is met on master: asks-done refuses a retry on a logged ask, naming the logged outcome, and `--correct` fixes it. Ruled by the lane session, 2026-11-11.
