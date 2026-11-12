---
type: "Change"
change_type: "fixed"
title: "Review launch deletes the run-folder inputs it read and stops older loops of the same repo"
description: "review_launch deletes the --fix and --handoff files it read from the code-phase run folder, so a failed Write of the next findings or handoff file makes the next launch fail on a missing file instead of running a fix loop on the previous run's findings. Before it starts, it stops every live earlier loop of the same repo and waits for it to exit, so two loops never edit one tree."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-11T23:53:09-06:00"}
seq: 12
kind: "fix"
components: ["script/review-fix", "skill/review", "skill/fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_launch.py::ReviewLaunchTest::test_a_launch_deletes_the_run_folder_inputs_it_read_and_keeps_a_review_stop"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/review_launch.py` `command_launch`:

- after the launch record is written, deletes each `--fix` or `--handoff` file whose folder is the code-phase run
  folder (`code_wait.PHASE_DIR_NAME`). The asks findings file and files elsewhere stay. Their text is already copied
  to the loop folder.
- before it starts the loop, reads each live `loops/*/loop.pid` (`reviewer_dispatch.live_loops`), checks that the
  loop's launch record names the same repo and that the pid's command line names the loop's agent id, sends SIGTERM to
  its process group, and waits up to 5 s for it to exit. A failed `ps`, kill or record read is printed on stderr and
  the launch goes on.

`lib/process_group.py` is new: a process's command line and a SIGTERM to its group.

## Evidence

judgment: four /review and /fix runs started a fix loop on the previous run's handoff or findings file after a failed
Write; in one, an orphan loop and a new one edited the tree together. The new launch tests fail on the old code.

## Result

`bash tests/run.sh` passes on the branch.

## Watch

—

## Back-out

Remove `consume_run_folder_inputs`, `stop_earlier_loops`, `stop_loop_if_live`, `wait_for_exit` and `loop_repo` from
`review/review_launch.py`, and delete `lib/process_group.py` and its test.
