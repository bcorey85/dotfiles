---
type: "Change"
change_type: "fixed"
title: "The code phase end runs the change-file check"
description: "A /code phase that changes toolkit paths now fails a change-file check before the Phase Status tick, naming the paths and the build_changes.py new command, instead of printing a commit subject that the pre-commit hook then refuses."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T18:14:50-06:00"}
seq: 5
kind: "fix"
components: ["script/code-step", "skill/code"]
evidence: ["tests/scripts/test_phase_change_file.py", "tests/scripts/test_pre_commit_hook.py"]
watches: []
test: "tests/scripts/test_phase_change_file.py::PhaseChangeFileTest.test_an_untracked_toolkit_file_without_a_change_note_fails_naming_the_path"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`.githooks/change-file-check` owns the toolkit and change-note path patterns and reads the `git diff --name-status -z` stream, so a path with a tab, a newline or an accent stays one path; a status that is not one capital letter exits 2. The pre-commit hook calls it. `phase_change_file.py` feeds it the work tree's changes plus each untracked file, passes its refusal through and adds a last line naming the next step; a repo without the check passes. The /code skill runs `phase_change_file.py` before the coder that ticks the phase.

## Evidence

`test_phase_change_file.py` pins an untracked and a modified toolkit path (including tab, newline, quote and accented paths) failing with the real path, an added change note passing, a repo without the check passing and a bad status exiting 2. `test_pre_commit_hook.py` pins the hook refusing staged tab, newline and accented toolkit paths. Rule meter for the skill line, scenario CK03 (run as CS03 at agent-evals e7fef959), opus at the competing level, 8 runs per arm: rule on 8/8, rule off 0/8, +100 points.

## Result

Before, the phase printed a commit subject with no change file and the hook refused the commit; now the phase end fails first and the run files the change file.

## Watch

—

## Back-out

Remove `.githooks/change-file-check` and `phase_change_file.py`, put the pattern block back in `.githooks/pre-commit`, and drop the `phase_change_file.py` clause from the skill step.
