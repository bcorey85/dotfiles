# code-step-scripts-nov25: resume base after a ticked phase, plan-folder rulings, phase-end change-file check, denied coder git writes

Source: ~/agent-evals/queue/phase-start-resume-keeps-an-earlier-phase-s-base.md
Source: ~/agent-evals/queue/plan-check-owner-disagrees-between-the-plan-dir.md
Source: ~/agent-evals/queue/code-phase-stop-skips-the-change-file-check.md
Source: ~/agent-evals/queue/code-run-stops-when-its-coder-is-denied-git-add.md

Four claimed queue items. Their text is the contract.

## 1. phase-start-resume-keeps-an-earlier-phase-s-base

After Phase N was committed, `/code resume` for Phase N+1 printed Phase N's start head as the base. Fix: when the
record's phase is ticked, a resume starts a new record at HEAD.

## 2. plan-check-owner-disagrees-between-the-plan-dir

`plan_check.py owner` on a plan directory answers `user` with ticket null; on the directory's spec.md it answers
`session`. The directory form should resolve the spec and ticket the same way the file form does. Also seen:
`review_fix.py decide --plan <plan dir>` crashes with IsADirectoryError in `plan_format.append_deviation`.

## 3. code-phase-stop-skips-the-change-file-check

A /code phase changed toolkit files and stopped with a commit subject but wrote no change file; the pre-commit hook
refused the commit. Fix: the phase-end step runs the pre-commit hook's change-file check on a toolkit-changing phase
before it prints the commit subject.

## 4. code-run-stops-when-its-coder-is-denied-git-add

A /code fork put stage and commit steps in its coder's prompt; the coder was denied `git add`, and the fork stopped
before review.

Done when: A /code run whose coder finishes with uncommitted changes commits them through the code step and goes on to
review, with no stop; a test of the code step covers the denied-coder-commit case.
