# Acceptance criteria

- **AC1** — `phase_start.py --resume`, when a commit since the start record's head ticks a phase in a plan's
  `## Phase Status`, prints HEAD as the base and writes a new record at HEAD, with a stderr note that names the plan
  and the phase. A resume with no ticked phase since the record keeps the record's head as now. (Phase 1)
- **AC2** — `plan_check.py owner` on a plan folder and on the plan file inside it gives the same owner and ticket.
  (Phase 2)
- **AC3** — `review_fix.py decide --plan <plan folder>` appends its `## Plan Deviations` entry to the plan file in that
  folder, with no crash. (Phase 2)
- **AC4** — At the phase end, before the commit subject is printed, a phase that changes toolkit paths and adds or
  changes no `docs/changes/notes/20*.md` file fails a check that names the paths and the `build_changes.py new`
  command. The run then files the change file and runs the check again. A repo without the check passes. The
  pre-commit hook and the phase-end check read one copy of the path patterns. (Phase 3)
- **AC5** — The /code skill tells the fork to put no stage or commit step in a coder prompt (a commit the task asks for
  becomes the phase-end commit subject), and says that a coder's denied git write does not stop the run: it goes on to
  review with the changes uncommitted. A test of the skill text covers the denied-coder-commit case. (Phase 4)
- **AC6** — `bash tests/run.sh` passes.
