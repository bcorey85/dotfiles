---
type: "Change"
change_type: "fixed"
title: "A plan run keeps its plan through asks-done and a finished planless run stops"
description: "A task file that opens with a plan now runs that plan, so asks-done returns to the run's own phase commit. A bare resume at a finished planless run now stops with that run's commit command, and a ruling correction at the asks stage now applies the rulings. Before, each of these left the work on a planless run that a later resume restarted at Phase 1."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T10:31:35-05:00"}
seq: 354
kind: "fix"
components: ["script/code-step", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_resume.py::ResumeTest::test_a_plan_run_started_from_a_task_file_walks_through_asks_to_its_own_commit_block"
asked: ""
proof: []
unmeasured: "No intake number reads this: a task-file start with a plan, the planless stop and the corrected ruling are not told apart from other starts and verbs in the logs."
---

## Change

- `carry_task_file_plan` in `code_step_start_args.py`: the first word of a task file (after a `Repo:` line) is read as a plan under the positional rule, with a leading `Phase <id>` or `--phase <id>` and the rest of the file as run notes, line breaks kept. A plan outside the repo stops at the question that asks for one inside it.
- `go_on_after_done` in `code_step.py`: a finished run with no plan on its own branch goes to `stop_for_finished_planless_run`; any other finished run goes on as before.
- `finish_planless` saves the run's commit files, and the stop says the commit command for only those files that are still dirty, or names `start <plan>` when none are.
- `run_verb` in `code_step.py`: `correct-ruling` on a run at the asks stage runs `asks-done` with the same words and `--also` text.
- /code skill rule 5: it covers messages, not the call's own args. The lines are sent to the sender and the run goes on only for `go-on` and for the `stop` that lists several checkouts, says another verb is running, says `--repo` is no git path or names no run, or names a state file to delete. Any other printed ACTION is followed under rule 2 and nothing is sent, so a finished run's commit command reaches the hand-back.

## Evidence

- A plan task sent through a task file ran planless, so no Phase Status box was ticked. Then a fork that was given `asks-done` as its args ran `correct-ruling` and was refused. Then a bare resume at the finished run opened Phase 1 over the uncommitted work.

## Result

- `tests/scripts/test_code_step_resume.py`: a task-file plan run walks through asks to its own commit block with the box ticked. A bare resume at a finished planless run stops and starts no run, with or without uncommitted files, and on another branch it does not stop on that run.
- `tests/scripts/test_code_step_start_input.py`: a task file with or without a `Repo:` line runs the plan with its notes kept, and text that does not open with a plan stays planless.
- `tests/scripts/test_code_step.py`: at the asks stage a correction dispatches the asks coder, and a rejection of a planless run's ask says the commit command.

## Watch

None; see `unmeasured`.

## Back-out

Revert the commit. A task file is read as planless task text, a bare resume at a finished planless run starts the branch's plan, and a correction at the asks stage prints the refusal again.
