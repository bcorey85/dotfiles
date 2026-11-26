# Durable lane plan: a plan folder for a repo with no docs/plans survives a reboot

A lane in a repo with no `docs/plans` kept its plan, decision log and acceptance criteria in the tmpfs scratchpad. A
reboot wiped them, and verify-prep then exited 4 (no plan). Give such a repo a plan folder under the worktree's git
dir (`git rev-parse --path-format=absolute --git-dir`, then `claude-plans/<slug>/`). It survives a reboot, adds no
file to the repo's tracked tree, and the shared resolver finds it. Source:
`~/agent-evals/queue/a-lane-plan-and-its-criteria-in-the-tmpfs.md`.

## Scope

- In: `claude/.claude/scripts/tools/resolve-task-dir.sh`, `claude/.claude/scripts/review/verify-prep` (the exit-4
  message), `claude/.claude/skills/eng-spec/phases/1-ticket.md` step 3,
  `claude/.claude/skills/verify-branch/SKILL.md` exit-4 row, and tests under `tests/scripts/`.
- Out: `skills/adr/scripts/adr_flow.py` (its task-dir deletion keeps to `docs/plans`), every other `docs/plans/<slug>`
  mention in skills and agents (they read the file beside the plan), settings.json, any CLAUDE.md.

## Phase Status

- [x] Phase 1: the resolver finds and names the git-dir plan folder; verify-prep's exit 4 names it (risk: medium)
- [x] Phase 2: eng-spec opens the task directory the resolver names (risk: low)
- [ ] Phase 3: verify-branch's exit-4 row writes the ticket to the path verify-prep names (risk: low)

## Phase 1: the resolver finds and names the git-dir plan folder; verify-prep's exit 4 names it

1. `resolve-task-dir.sh`: the git-dir plan root is `<git dir>/claude-plans`, where `<git dir>` is
   `git rev-parse --path-format=absolute --git-dir` run in the current folder (the worktree's own git dir). Outside a
   git repo there is no git-dir root.
2. New verb `--home <slug>`: print `docs/plans/<slug>` when the current folder has a `docs/plans` directory, else
   `<git dir>/claude-plans/<slug>` (absolute). Exit 0. A missing or empty slug, or a slug with a `/`, exits 2 with a
   usage line on stderr. Outside a git repo with no `docs/plans`: exit 2 naming both.
3. Ticket lookup: after `docs/plans` and `docs/eng-specs`, the task-dir glob also searches
   `<git dir>/claude-plans/<TICKET>/` and `<TICKET>-*/`. Matches count with the others (one → exit 0, several → 3).
   Printed paths under the git-dir root are absolute.
4. No ticket in the argument or branch name: when `<git dir>/claude-plans/` holds exactly one folder, print it and exit
   0; several, print all and exit 3; none, exit 4 as today.
5. Update the header comment: the git-dir root, `--home`, and that its paths print absolute.
6. `verify-prep` exit 4: the message names the ticket path `<git dir>/claude-plans/<KEY>/00-ticket.md` (with the real
   absolute git dir of the repo top) in place of `<scratchpad>/<KEY>-ticket.md`, and says the folder survives a
   reboot; the rerun stays `--ticket-file <that path>`.
7. Check every caller still reads the output: verify-prep (`top / output` keeps an absolute path), `adr_flow.py`
   (reports a git-dir task dir as a problem, which is right for deletion), `skills/code/SKILL.md` step 0.

8. Tests: new `tests/scripts/test_resolve_task_dir.py` (script path from an env var defaulting to this tree's
   script): a fixture repo with no `docs/plans` and a ticket branch finds `<git dir>/claude-plans/<TICKET>-x/`; a
   ticketless branch finds the single folder there and exits 3 on two; `--home` prints `docs/plans/<slug>` with a
   `docs/plans` folder and the git-dir path without one; in a linked worktree `--home` and the lookup use that
   worktree's git dir; a bad slug exits 2. A verify-prep test: a fixture repo with no `docs/plans` whose plan folder
   (`plan.md` + `acceptance-criteria.md`) sits in the git-dir root resolves with no arguments; the exit-4 message names
   the git-dir ticket path.

#### Automated Verification

- [ ] **Resolver tests**: `python3 tests/parallel_tests.py test_resolve_task_dir.py`
- [ ] **verify-prep tests**: `python3 tests/parallel_tests.py test_verify_branch_script.py`

## Phase 2: eng-spec opens the task directory the resolver names

1. `skills/eng-spec/phases/1-ticket.md` step 3: "Open the task directory `docs/plans/<slug>/`" becomes "Open the task
   directory that `bash ~/.claude/scripts/tools/resolve-task-dir.sh --home <slug>` prints". The slug rules stay.
2. Ruled by agent-evals-74 (2026-11-26): ships `unmeasured` in its own change file and its own commit.

#### Automated Verification

- [ ] **Anchors**: `bash claude/.claude/scripts/tools/rule-anchors.sh check`

## Phase 3: verify-branch's exit-4 row writes the ticket to the path verify-prep names

1. `skills/verify-branch/SKILL.md` exit-4 row: "write its raw fields to `<scratchpad>/<KEY>-ticket.md`" becomes
   "write its raw fields to the ticket path the message names".
2. Ruled by agent-evals-74 (2026-11-26): ships `unmeasured` in its own change file and its own commit.

#### Automated Verification

- [ ] **Anchors**: `bash claude/.claude/scripts/tools/rule-anchors.sh check`
- [ ] **Full suite**: `bash tests/run.sh`
