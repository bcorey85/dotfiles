# Acceptance Criteria — toolkit-scripts-1122

> Written before implementation. The closing Verify phase reconciles these
> against the test suite.

Item 1 (review-commit-gate-places-a-cd-to-a-literal-repo) is dropped by decision D1: its gate no longer exists, so it carries no criteria.

## Item 2 — guide skill (ticket criteria, verbatim)

- **AC1** — The skill keeps one worked card and points to the binary for the format; the dropped rules pass rule-meter or stay; `bash tests/run.sh` passes.
  - Cut with every guide deliverable at the rebase onto master (D20): master deleted the guide skill.
  - Narrowed under D8 (03-decisions.md sign-offs): "points to the binary for the format" is narrowed out of this branch. `guide --format-version` prints a version, not a schema, so the tables stay (D8). The pointer waits on a guide build that prints the schema.

## Item 3 — refactor skill (ticket criteria, verbatim)

- **AC2** — `refactor_flow.py` prints the template (a verb or --help); the skill keeps about 3 lines that name the trigger to run it; the refactor tests and `bash tests/run.sh` pass.

## Item 4 — mutation-tester (ticket criteria, verbatim)

- **AC3** — A script under claude/.claude/scripts/ does lock, backup and restore with tests under tests/scripts/; the agent calls it in one line; the precondition count is right; the opencode port is patched; `bash tests/run.sh` passes.
  - Met as ruled in 03-decisions.md sign-offs: "the agent calls it in one line" is met by three one-line calls, one per step (`check`, `lock`, `restore`; AC23).

## Derived from the plan

### Refactor log template

- **AC4** — Running the refactor script's `log --help` prints the log input template as JSON between two marker lines, and that JSON, saved as the input file, logs successfully in branch mode on the first call.
- **AC5** — Log input files written before this change still parse and log exactly as before, and the refactor script keeps every other verb, argument and exit code.
- **AC6** — The refactor skill's logging step has no JSON example and no key list, and still names when to log, the command to run, where the input shape is printed, and the three judgment rules (one entry per smell, never escape sweep matches or legacy targets, the `miss_reason` source), worded as before with their key lists stripped (the exact text is in the plan's Phase 2).
- **AC7** — The close-branch skill tells the reader to get the log input shape from the refactor script's `log --help`, not from the refactor skill.
- **AC8** — The refactor script file is at most 1000 lines after the grammar moves out.

### Calibration lock owner

- **AC9** — The calibration guard behaves exactly as before for every lock state (no lock, live lock, stale lock, legacy-path lock): same output for plain paths; a path with shell characters comes out as one pasteable shell word; same exit code.
- **AC10** — The lock path, its fallback, the timestamp form and the liveness rule are defined in one module that both the guard and the new mutation script use.

### mutation_lock script

- **AC11** — `check` on a regular, in-tree file of a git repo with no lock prints a `NEXT:` line, exits 0, and writes no lock and no backup; on a target with uncommitted or untracked edits, `check` and `lock` still proceed and print one `NOTE:` line naming the file and its `git status --porcelain` line (D18).
- **AC12** — `check` stops with a `STOP:` line and exit 1 for a missing file, a symlink, a folder outside any git repo, and a path outside the work tree, changing nothing.
- **AC13** — `check` and `lock` stop with a `STOP:` line and leave the existing lock byte-for-byte unchanged when a live lock, a stale lock or a legacy-path lock exists; a stale or legacy lock's stop shows the locked file, the backup path and the recovery commands.
- **AC14** — `lock` saves a byte-identical backup of the target, writes a lock with the same fields and types the guard reads today (UTC timestamp in the guard's form, integer owner pid, 16-hex pre-hash, worktree-relative file), and the calibration guard reads that lock as live while its owner runs.
- **AC15** — `lock` refuses to run when a lock already exists, and when the target is too large to back up it stops and writes no lock.
- **AC16** — `restore` after an edit puts the target back byte-identical, verifies its hash, removes the lock, exits 0 and ends with a `DONE:` line; with no edit it also exits 0 and says the file was already identical.
- **AC17** — `restore` with a backup that no longer matches the recorded hash exits 3, keeps the lock, and prints the target path and the backup path.
- **AC18** — `restore` refuses a lock written by another writer or another owner pid (printing the `cp <backup> <target> && rm <lock>` recovery line, each path printed as one pasteable shell word (double quotes, or single quotes when the path holds a character double quotes would expand or end on)), a missing lock, a missing backup, and a lock found only at the legacy path, each with a `STOP:` line, leaving the target and lock untouched.
- **AC19** — `restore` on a lock written by the old prose procedure (old backup layout) keeps the lock, exits 1 and prints the manual `cp` and `rm` recovery lines.
- **AC20** — If the lock cannot be removed after a verified restore, `restore` exits 1 with a `STOP:` line giving the exact `rm` command for the caller.
- **AC21** — Every verb's output ends with a `NEXT:`, `STOP:` or `DONE:` line.
- **AC22** — `mutation_lock.py --help` lists every precondition the script checks, in check order, and that list is the only place the checkable preconditions are enumerated.

### mutation-tester prompts

- **AC23** — Both the Claude and the opencode mutation-tester prompts do lock, backup and restore with one `mutation_lock.py` line per step, using only the verbs `check`, `lock` and `restore` and only flags each verb accepts.
- **AC24** — Neither prompt names a calibration state path, the legacy lock path, `jq`, `sha256sum`, or a precondition count ("all four" or "all five"), and Step 0 keeps as prose only the two preconditions a script cannot check (the dispatch names a test command, the dispatch names the file).
- **AC25** — The mutation-tester still tells the agent to restore by the script only, never by `git checkout`, `Write` or `Edit`, to stop loudly on a hash mismatch, and, on any other `STOP:`, to print the exact command for its caller and never retry by another route.

### guide skill and rule-meter

- **AC29** — Each new rule-meter detector grades a compliant reply, a violating reply, and a reply with no parseable batch (or under two cards) as COMPLIED, VIOLATED and NO_TEST respectively, and `rule_meter.py` is unchanged.

### Toolkit bookkeeping

- **AC30** — Every changed anchored prompt section has its `docs/rule-anchors.md` row rehashed and linked to a change note, and the anchors check passes.
- **AC32** — `bash tests/run.sh` passes on the branch, and `bash tests/lint.sh` passes on every changed script.

## Manual only

- **AC26** — The guide skill has one worked card ("a judgment call with evidence") and no A/B or rating card, while its commands block, batch keys, card envelope, block and field tables, and rules 1, 2 and 6 are unchanged. Manual only: D9: no test reads the guide skill; the Phase 6 `rg` checks and a read of the file verify it. Cut under D20 (03-decisions.md): master deleted the guide skill.
- **AC27** — A guide rule among 3, 4, 5 and 7 is removed only when rule-meter on and off arms, two graded runs per cell at every level, show the off arm complying at least as often as the on arm; any rule the meter cannot grade stays, rule 8 stays, and the remaining rules are numbered 1..N with no gap. Manual only: meter runs are agent-run against `results.jsonl`; no suite test reads the meter. Cut under D20 (03-decisions.md): master deleted the guide skill.
- **AC28** — The guide change note records each rule's per-level on and off counts, lists rule 8 and any ungradeable guide rule under `unmeasured` (the mutation-tester change note lists the Step 4 gate sentence under `unmeasured`, D13), and states that cutting the format tables waits on a `guide` build that prints the schema. Manual only: a change note's content is read, not tested; `build_changes.py --check` checks only the index. Cut under D20 (03-decisions.md): master deleted the guide skill.
- **AC31** — A change note exists in this worktree's `docs/changes` for each of the three items, and the change index checks clean. Manual only: `build_changes.py --check` is a bookkeeping command, not a suite test. Two notes after D20: the guide note is cut with the guide item.
- **AC33** — A human running `/guide` can still follow the trimmed skill and produce a valid batch from the kept card and tables.
  No test reads the guide skill and the `guide` binary is not installed here (D9). Cut under D20: the skill is deleted on master.
- **AC34** — The Step 4 gate-block rule of the mutation-tester ("hand the command to the caller, never retry another way") still binds the agent after its trigger was reworded.
  No scenario can make the script's unlink fail on demand, so the meter cannot grade it (D13).
