---
type: "Change"
change_type: "fixed"
title: "Phase review asks need a ruling before the commit"
description: "When a /code phase review hands back reviewer questions, the commit gate refuses any session's `git commit` in that repo until `phase_asks.py rule` records accepted or rejected, with a reason, for each one."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-13T21:25:01-06:00"}
seq: 4
kind: "fix"
components: ["script/review-commit-gate", "script/phase-asks", "script/code-wait", "script/handback-store", "script/code-review-start", "script/shell-command", "script/script-utils", "script/handback", "script/review-asks", "script/review-fix", "script/file-lock", "skill/code"]
evidence: ["half-of-the-reviewers-questions-in-a-code-run"]
watches: ["phase-asks-need-a-ruling-before-the-commit"]
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_converged_review_with_phase_asks_not_ruled_on_denies_the_commit_and_names_the_rule_command"
asked: ""
proof: []
unmeasured: "The code skill's converged bullet swaps a hand-typed log call for the `phase_asks.py rule` line that `code_wait.py review` prints. No rule-meter fixture shows a /code fork's converged step, so the wording has no meter run; the commit gate and its tests hold the behavior. Accepted unmeasured by the user on 2026-11-14 (\"ship\"), confirmed by the user in the lane session the same day. The `deferred` bullet's wording (handle as `converged`, asks and the rule line included) has no meter run either; session agent-evals-7f relays the user's \"1. yes\" to it, typed in that session's pane on 2026-11-14. A later rewording of the converged bullet (the fork runs `phase_asks.py list`, rules on every ask it prints, and runs the rule line it prints) has no meter run and is not yet accepted by the user."
---

## Change

- `code_wait.py review`: when a clean phase packet holds a finding ask, it records a `phase-asks-open` row in the hand-back store and prints the `phase_asks.py rule` line to run. `code_review_start.py` writes `<git dir>/code-phase/run.json` with the lane and phase, which that row carries.
- New `review/phase_asks.py`: `list` prints the open asks and the rule line; `rule '<accepted|rejected>:<one-line reason>' ...` takes one word per ask in order, logs each outcome with `decided_by=session`, and records a `phase-asks-ruled` row. A wrong count, a missing reason or another word exits 2.
- `review_commit_gate.py`: `check_commit` denies while the repo has an open-asks row with no ruling, before the all-clear return. A later review of the repo leaves the asks open; only a ruling settles them. The denial names the rule line.
- New `review/commit_gate_denials.py` holds that denial and the plan-impact denial, moved out of the gate (998 to 976 lines) with its text unchanged.
- `handback_store.py`: the two row kinds, `record_phase_asks_open`, `phase_asks_state` and `unruled_phase_asks`. They read every session's file by repo (a new session id still meets the asks); a ruled row names the open row it answered (`open_ts`); a replayed packet that was ruled opens nothing; a damaged phase-asks row raises `PhaseAskRowError`.
- `skills/code/SKILL.md`: the converged bullet runs the printed `phase_asks.py rule` line in place of a hand-typed `log-review-finding` call; the `deferred` bullet handles the packet as `converged`.
- `handback.py` `run_logger` and `script_utils.run_command_result`: the log helper call with a timeout.

## Evidence

Queue item `half-of-the-reviewers-questions-in-a-code-run`: 332 of 653 reviewer questions in /code runs have no outcome row. The log call was a prose step with nothing checking it.

## Result

The named test fails on the old gate (the commit is allowed) and passes with the change. `tests/scripts/test_phase_asks.py` adds 56 tests; `test_review_commit_gate.py` and `test_code_review_start.py` add 32; `test_shell_command.py` adds 10; `test_script_utils.py` adds 1; new `test_file_lock.py` has 4.

`tests/scripts/test_phase_asks_chain.py` (5 tests) runs the chain as real processes: `code_review_start.py --detach` runs the loop's own entry, which builds the packet and writes the hand-back rows; `code_wait.py review` opens the two asks; the gate hook denies `git commit`; the command the denial prints rules one accepted and one rejected; the gate then passes and both outcome rows hold the asks' finding ids. A ruling with one word for two asks exits 2 and the commit stays denied. A failing ledger leaves the ruling standing. Only the loop's walk is a stand-in (a fixed outcome), so no model call runs. With the telemetry switch off the rows still land: `log-review-finding` writes to the ledger whatever the switch says.

Suite: `bash tests/run.sh` passes, 4075 tests in 145 files, 0 failed, after the merge of master.

The branch-wide review led to three more fixes: a clean packet opens its asks with no stored hand-back row; `phase_asks.py` exits 2 outside a work tree; the gate reads the rule line from the new `lib/ask_outcome_words.py` and no longer imports `phase_asks`.

A second branch-wide review led to two more: a packet opened while earlier asks have no ruling carries those asks into its open row, each with its own context, so one `rule` call settles all of them; the code skill's `deferred` bullet handles the packet as `converged`, asks and the rule line included.

A stress test by another session led to five more, each with a test: open asks are read by repo across sessions, and the gate checks them in a session with no review events; a ruling settles only the open row it names; a ruled packet opened again opens nothing; a damaged row denies the commit and stops `phase_asks.py`, naming the file and line, and a store that cannot be written stops `rule` before it logs; the log helper call has a 30 s timeout (`handback.run_logger`), and after one timeout the `rule` run makes no more log calls, prints each row's command to log later, and records the ruling.
A third branch-wide review led to nine more: a commit after a `cd` is checked against the repo it lands in; `code_wait.py review` prints the count of all open asks; a torn row stops the read only when it names this repo; a row holds only `contexts` and `packet_keys`; `rule` with no session id exits 2; the ruled row goes to the file of the session that opened the asks; the outcome words moved to `lib/ask_outcome_words.py`; the gate's docstrings say a merge is denied while asks are open.

A review by another session of the commit's placement led to three more: the gate reads the repo from what the command names (each literal `cd`, `pushd` and `git -C` target before the commit, a subshell's included, else the hook's folder) through the new `shell_command.git_commit_dirs`; a commit is never denied for another repo's asks, and one the gate cannot place in a repo passes this check; one unreadable store entry is skipped, named on stderr, and the rest are read. `GIT_DIR` and `--git-dir` are not read.

A fourth branch-wide review led to ten more: a torn row counts for a repo only when it holds that repo's whole path; `shell_command.git_c_directory` is the one reader of a `git -C` dir, for commit credit and for this check; a `cd` inside `( ... )` stops counting when the group closes; `rule` writes a ruled row to the file of every open row it answers, so a pruned file brings no ruled ask back; the gate checks the asks before it reads the transcript; `code_wait.py review` outside a work tree opens nothing; the skipped-entry line starts `handback_store:`; `PhaseAskRowError` lost three attributes with no reader; two docstrings.

A second stress test by another session led to three more, each with a real-process test: a damaged row that names no whole repo is skipped with one stderr line, so a row cut inside the path stops no repo; four reviews landing at once keep every ask; two `rule` calls at once log each outcome once. The last two hold one `flock` lock per repo (`phase-asks-<hash of the repo path>.lock` in the store folder, new `lib/file_lock.py`) around the read and the append; after 30 s without the lock, `rule` exits non-zero, names the lock file and writes nothing, and `code_wait.py review` exits 1 with a last line that names its rerun. The gate's read takes no lock.

A fifth branch-wide review led to nine more: the gate follows `cd`, `pushd`, `popd` and `cd -` to the folder each commit runs in, leaves out a commit whose folder it cannot read (a `cd` to a variable, `env -C`, `--git-dir`), and falls back to the hook's folder only for a command it cannot read at all; the lock is per repo, so a hung log call in one repo holds no other; `code_wait.py review` exits 1 when the asks cannot be opened; the ruled row names the ruling session (`ruled_by`); `script_utils.can_append` replaces `phase_asks.store_writable`; the lock error alias with no reader is gone; the code skill's converged bullet rules on the asks `phase_asks.py list` prints.

## Watch

`phase-asks-need-a-ruling-before-the-commit`: share of phase reviewer questions with an outcome row (metric `phase_asks_with_outcome_share`), expected up. Before: 152 of 392.

## Back-out

Revert the commit.

