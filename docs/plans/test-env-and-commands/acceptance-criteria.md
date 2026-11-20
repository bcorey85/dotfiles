# Acceptance criteria

- **AC1** — In a linked worktree with no `.python-version` while the main checkout pins one, the full check, the hand-back gate and the criteria dry run all run with the pyenv shims first on PATH and the main checkout's version selected. (Phase 1)
- **AC2** — herdr-worktree symlinks a gitignored `.python-version` from the main checkout into the new worktree, and `git status` there stays clean; a tracked or non-ignored file is not linked. (Phase 1)
- **AC3** — With `Pipfile.lock` (or another lock-file runner) present but the tool not on PATH and a project `.venv`/`venv` present, gate and discovered check commands use the venv python. (Phase 2)
- **AC4** — A check that exits 127 on a missing tool is reported naming the tool as an environment gap: the full check says `not run (environment gap: ...)`, the hand-back gate's setup-fault stamp names the tool and does not block or count, the criteria dry run gives ENV with the fix named, never BROKEN. (Phase 2)
- **AC5** — The discovered full check runs only the parts (frontend package, Python backend) whose path kind a changed path has, every part when a changed path is outside all of them, and a part that cannot start does not stop the other parts from running and reporting. (Phase 3)
- **AC6** — A Django test-database collision in the hand-back gate or the full check is retried once; a pass on retry counts as a pass, and a second collision is a setup fault naming the collision and the fix, never a counted attempt or a blocker. (Phase 4)
- **AC7** — A `--test` command replaces the default full check after a setup fault or after an overridden run (`check_overridden` is recorded in the packet); on any other launch it stays a scoped gate. A setup fault in the overriding `--test` command itself stops the loop as `setup-fault`. (Phase 5)
- **AC8** — Failing-test extraction ignores logger lines (`ERROR django.request ...`, `ERROR: message`) and still lists unittest `FAIL:`/`ERROR:` headers and pytest `FAILED <node>` lines. (Phase 6)
- **AC9** — A scoped failure whose head and base logs differ only in Python traceback line numbers is read as pre-existing and does not stop the loop. (Phase 6)
- **AC10** — The quality-check cap allows a rerun that adds or changes a leading `NAME=value` prefix, and a failed run whose output shows the tool could not start, or an environment fault with no runner summary, is not recorded. (Phase 7)
- **AC11** — No gate command from gate_commands.py contains `cd` or `&&`; package commands use the manager's folder flag and `{files}` still resolves. (Phase 8)
- **AC12** — A diff whose changed files under a Rust crate are all non-Rust gives no cargo command. (Phase 8)
- **AC13** — verify-prep's printed run rules tell the verifier to keep the default TMPDIR for test runs. (Phase 9)
- **AC14** — `bash tests/run.sh` passes (test_rule_anchors failing on master excepted).
