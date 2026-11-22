# Gates batch: a split delete that empties a directory, and an unnamed docker run

Two queued toolkit defects, both folded into the existing PreToolUse(Bash) gate `gates/git_discipline_gate.py`
(no new hook process, no `settings.json` edit). `bash-safety-gate.sh` is generated and is never edited. Each phase
starts with a test that fails on the current tree. Scripts live in `claude/.claude/scripts/`; tests in
`tests/scripts/`, paths from `tests/scripts/toolkit_paths.py`. Follow `docs/toolkit-script-rules.md` and
`claude/.claude/scripts/CLAUDE.md`: one owner per fact, shell parsing only through `lib/shell_command.py`,
`lib/shell_statements.py` and `lib/shell_directory.py`; never a bare `shlex.split`, `str.split` or operator regex on
a command.

## Scope

- In: `gates/git_discipline_gate.py` (two new rules and their deny text, docstring updated), two new lib modules
  `lib/directory_emptying_deletes.py` and `lib/docker_run_names.py`, `tests/scripts/test_git_discipline_gate.py`,
  new `tests/scripts/test_directory_emptying_deletes.py` and `tests/scripts/test_docker_run_names.py`, the
  lib list in `docs/toolkit-script-rules.md`, the Owners list in `claude/.claude/scripts/CLAUDE.md`.
- Out: `bash-safety-gate.sh` (generated), `settings.json`, every file under `scripts/review/`, every agent or skill
  prompt, the omp bridge.

## Phase Status

- [x] Phase 1: a run of plain `rm` calls that empties a directory is denied like the recursive form (risk: medium)
- [x] Phase 2: a `docker run` without `--name` is denied with the fixed form (risk: low)

## Phase 1: a run of plain `rm` calls that empties a directory is denied like the recursive form

Bug: `bash-safety-gate.sh` denies `rm -r <dir>` (`rm_recursive_force`). A coder then deleted the directory's files
one by one (`rm dir/a`, `rm dir/b`, ... then `rmdir dir`) and every call passed. The hook has no state across calls,
so the check reads the file system: a plain `rm` whose targets cover every entry of an existing directory empties
it, and that is the recursive form split into files.

1. New `lib/directory_emptying_deletes.py`, the owner of "which directories a command's plain `rm` calls would
   empty". `emptied_directories(command, directory) -> list[str]`:
   - Read the command through `shell_statements.shell_code`, then `shell_command.split_command_steps` and
     `shell_command.segment_words`; peel wrappers with `shell_command.command_after_wrappers`. Follow a `cd` with
     `shell_directory.ShellDirectory` (start at `directory`), the way `lib/git_calls.py` places a call.
   - A step is an rm call when the basename of its command word is `rm` (not `git rm`: `rm` as the first word only).
     Its targets are the words that do not start with `-`, plus every word after `--`. A target with a mark the gate
     does not read (`$`, backtick, `~` not followed by `/` — `shell_directory.UNREAD_FOLDER` names them) is skipped;
     a glob target is expanded with `glob.glob` in the step's directory. `~/` expands with `os.path.expanduser`.
     A recursive rm (`-r`, `-R`, `--recursive`, a cluster holding `r` or `R`) is left to bash-safety-gate: skip it.
   - Collect the targets of every rm step of the command into one set of real paths. For each parent directory of a
     target: when the directory exists and every entry of `os.listdir` is in the set, it is emptied. A directory the
     gate cannot list (`OSError`) is not reported: that part fails open, with a comment that says so.
   - Not reported: a directory under a temp root (`hook_input.is_under_temp_dir`) and a directory whose path holds a
     build or cache folder name from a `SAFE_FOLDER_NAMES` constant (`node_modules`, `dist`, `.cache`, `coverage`,
     `.next`, `.nuxt`, `.turbo`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.tox`), the same
     allowances the generated gate makes for the recursive form.
2. `gates/git_discipline_gate.py`: rule 9, after the existing checks in `run`: for each emptied directory, raise
   `DenyError` with text that opens `[git-discipline-gate] rm of every entry in <dir> empties it:` and says that this
   is the recursive delete `bash-safety-gate` denies as `rm_recursive_force`, split into files; a blocked delete is
   never split or disguised; leave the files and report the delete as a stop, so the user can run `rm -r <dir>`
   themselves. The gate stays fail-closed on internal error (its existing `main`).
3. Docstring: add rule 9 to the module docstring in the existing style. `claude/.claude/scripts/CLAUDE.md` Owners:
   one line naming `lib/directory_emptying_deletes.py` as the owner of "which plain rm targets empty a directory".
   `docs/toolkit-script-rules.md`: add the module to both lib lists.

#### Automated Verification

- [x] New `tests/scripts/test_directory_emptying_deletes.py`: a fixture directory with two files; `rm d/a d/b` reports
  `d`; `rm d/a` alone with `b` still present reports nothing; `rm d/*` reports `d`; `cd d && rm a b` reports `d`;
  `rm d/a; rm d/b` in one command reports `d`; `rm -r d` reports nothing (left to bash-safety-gate); a directory
  under `/tmp` reports nothing; a `node_modules` directory reports nothing; a target holding `$VAR` reports nothing;
  `git rm d/a d/b` reports nothing; an rm in a heredoc body or a comment reports nothing.
- [x] `tests/scripts/test_git_discipline_gate.py`: a new test class: the deny text for `rm d/a d/b` on a fixture
  directory starts with `[git-discipline-gate] rm of every entry in`; `rm d/a` with `d/b` present passes;
  the last `rm d/b` after `d/a` is gone is denied (the cross-call shape: run the gate twice with the file system
  changed between).
- [x] `python3 tests/parallel_tests.py test_directory_emptying_deletes.py test_git_discipline_gate.py` passes;
  `bash tests/lint.sh` on the changed `.py` files passes.

## Phase 2: a `docker run` without `--name` is denied with the fixed form

Bug: a session hand-rolled a one-off `docker run` without `--name` or `--rm`; Docker picked a random name, the
process hung and the container ran for days with nothing tying it to a ticket or session.

1. New `lib/docker_run_names.py`, the owner of "whether a docker run names its container, and the fixed form".
   `unnamed_docker_runs(command, directory) -> list[str]`: the fixed form of each `docker run` or
   `docker container run` (also `podman`) step of the command that carries no `--name <value>` or `--name=<value>`
   word before the image. Read steps as in Phase 1, but peel wrappers with
   `shell_command.command_after_wrappers(words, peel_containers=False)` so the docker call itself is kept.
   `docker compose run` is not a target: compose names its containers. The fixed form is the step's words with
   `--rm --name <ticket>-<purpose>` inserted right after `run` (`--rm` only when the step has none), joined with
   `shlex.join`. `<ticket>` is the leading `KEY-123` of the branch `script_utils.current_branch(directory)` when it
   has one, else the literal `<ticket>`; `<purpose>` stays literal for the session to fill.
2. `gates/git_discipline_gate.py`: rule 10: for the first unnamed run, raise `DenyError` with text that opens
   `[git-discipline-gate] docker run without --name` and says that an unnamed container cannot be tied to a ticket
   or session, then `Run it as: <fixed form>` and that `--name` carries the ticket number and `--rm` removes the
   container at exit.
3. Docstring rule 10; Owners line for `lib/docker_run_names.py`; both lib lists in `docs/toolkit-script-rules.md`.

#### Automated Verification

- [x] New `tests/scripts/test_docker_run_names.py`: `docker run image cmd` gives
  `docker run --rm --name <ticket>-<purpose> image cmd`; `docker run --rm -v /a:/b image` gives one `--rm`;
  `docker run --name x image` and `docker run --name=x image` give nothing; `docker container run image` is read;
  `docker compose run web pytest` gives nothing; `docker exec c cmd` gives nothing; `timeout 60 docker run image`
  is read through the wrapper; a branch `ABC-12-desc` gives `ABC-12-<purpose>`; `echo "docker run image"` (quoted
  text, not a call) gives nothing.
- [x] `tests/scripts/test_git_discipline_gate.py`: `docker run image` is denied with text that starts with
  `[git-discipline-gate] docker run without --name` and holds `Run it as: docker run --rm --name`;
  `docker run --name x image` passes.
- [x] `python3 tests/parallel_tests.py test_docker_run_names.py test_git_discipline_gate.py` passes; lint passes.

## Testing Strategy

Each phase adds the tests above before the change and shows them failing on the current tree. The full suite,
`bash tests/run.sh`, runs once at branch end (not per phase). Hook time is measured at branch end by the session,
not by a coder.

## What We're NOT Doing

- No edit to `bash-safety-gate.sh` (generated) or `settings.json`; no new hook entry.
- No state across Bash calls: the file-system read catches the last delete of the run, which is the one that empties
  the directory.
- No `--rm` requirement on its own: a `docker run` with `--name` and no `--rm` passes; the fixed form adds `--rm`.
- No prompt text in agents or skills.

## Plan Deviations

- ruling, 2026-11-22, session (lane dotfiles-gates-nov22, criteria owner plan): SAFE_FOLDER_NAMES drops __pycache__ to match bash-safety-gate.sh; no list is shared with the generated file. AC1 unchanged.
- ruling, 2026-11-22, session (lane dotfiles-gates-nov22, criteria owner plan): rejected the plan impact that would deny only when the emptied directory holds an untracked or modified entry; AC1 and AC2 stay as written.
- ruling, 2026-11-22, session (lane dotfiles-gates-nov22, criteria owner plan): brace targets (rm d2/{a,b}), a cd inside a subshell and folder targets are known limits recorded in the module docstring of lib/directory_emptying_deletes.py; no code.
- ruling, 2026-11-22, session (lane dotfiles-gates-nov22, criteria owner plan): docker_run_names skips shell group words (`do`, `then`, `{`) at the start of the step text, so the fixed form is the docker command alone.
- ruling, 2026-11-22, session (lane dotfiles-gates-nov22, criteria owner plan): CLAUDE.md Owners lines ruled no by the user; the owner of directory_emptying_deletes, docker_run_names and shell_command_words.placed_raw_words is stated in each module docstring. A reviewer finding asking for a CLAUDE.md line is ruled no.
- ruling, 2026-11-22, session (lane dotfiles-gates-nov22, criteria owner plan): docker_run_names takes its ticket-key pattern from lib/plan_format.py TICKET_KEY (MOVED_TARGET and adr_flow.py unchanged) and its boolean option table from lib/shell_command.py DOCKER_RUN_BOOLEAN_OPTIONS, beside DOCKER_VALUE_OPTIONS.
- ruling, 2026-11-22, session (lane dotfiles-gates-nov22, criteria owner plan): docker global options before `run` (`docker --context x run img`) are a known limit stated in the docker_run_names docstring; no code.
- ruling, 2026-11-22, session (lane dotfiles-gates-nov22, criteria owner plan): reword only, no criterion changed: Phase 2 step 1's "joined with `shlex.join`" is read as "spliced into the step's own text", so quoting, expansions and redirections of the original step survive and the `<ticket>-<purpose>` placeholder stays unquoted.
- ruling, 2026-11-22, session (lane dotfiles-gates-nov22, criteria owner plan): supersedes the "MOVED_TARGET and adr_flow.py unchanged" note: TICKET_KEY (`[A-Z][A-Z0-9]+-\d+`) is the one ticket-key grammar; adr_flow.py's TICKET_KEY_PATTERN is built from it with its behaviour unchanged, and MOVED_TARGET now needs a two-character key, matching adr_flow and `_shared/jira-ticket.md`. Branch-prefix handling (`feature/KEY-1`) stays separate in each reader; no session hit the difference.
