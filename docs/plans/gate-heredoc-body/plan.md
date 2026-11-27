# git-discipline-gate rule 11: a heredoc body written to a file is no commit

Rule 11 denies `cat > f <<'EOF'` whose body holds `git commit -m x` in a shared clone: `git_commit_dirs` in
`lib/git_commit_calls.py` reads the raw command, so `placed_commands` reads each heredoc body line as a command.
`lib/shell_statements.py` `shell_code` already owns the cut: it removes a body that only stores text, keeps a body fed to
a shell (`bash <<EOF`, `sh <<'EOF'`, `cat <<EOF | bash`) wrapped in `(` `)` lines, and keeps the `$(...)` spans of an
unquoted body. Every other gate reader (`git_calls`, `memory_cap_scope`, rule 8) already reads `shell_code`.

## Scope

- In: `claude/.claude/scripts/lib/git_commit_calls.py`, `claude/.claude/scripts/gates/git_discipline_gate.py`
  (`is_sole_git_command`), `tests/scripts/test_git_discipline_gate.py`.
- Out: `lib/shell_statements.py` (the owner; no change), settings.json, every CLAUDE.md.

## Phase Status

- [x] Phase 1: commit readers read stored-heredoc-cut text (risk: low)

## Phase 1: commit readers read stored-heredoc-cut text

1. `git_commit_dirs` passes `shell_statements.strip_stored_heredocs(command)` to `placed_commands`, not the raw
   command. Its docstring says heredoc bodies that `cat`/`tee` write to a file or a script run reads are not read.
2. `is_sole_git_command` in the gate reads the same `strip_stored_heredocs` text, so its "called only after
   git_commit_dirs has read the command, so it parses" holds.
3. Tests in `SharedCloneCommitTest` through the hook process (`assert_shared_allowed` / `assert_shared_denied`):
   - allowed: `cat > f <<'EOF'` and `cat > f <<EOF` with body `git commit -m x`;
   - denied: `bash <<EOF`, `sh <<'EOF'` and `cat <<'EOF' | bash` with the same body; an unquoted body holding
     `$(git commit -m z)`; a stored heredoc followed by a bare `git commit -m y` line.

#### Automated Verification

- The allowed test fails on the base tree and passes after.
- `python3 tests/parallel_tests.py test_git_discipline_gate.py test_shell_command.py` passes.
- `bash tests/lint.sh` on the three changed .py files passes.

## Plan Deviations

- Phase 1 readers use `strip_stored_heredocs`, not `shell_code`: `shell_code` cuts every body not fed straight to a
  shell, so rule 11 would miss `source /dev/stdin <<EOF`, `xargs sh -c <<EOF`, `while read` loops and
  `{ cat <<EOF; } | bash`, which the base denies. Ruled by the orchestrating lane session (fix/gate-heredoc-body),
  2026-11-26; criteria owner `plan`, AC1 and AC2 unchanged.
- Write-then-run in one command (`cat > run.sh <<'EOF' ... EOF` then `bash run.sh`, `source run.sh`, `. ./run.sh`)
  is now allowed by rule 11; the base denied it only because it read every body line, and no session hit it. Accepted
  as part of the existing limit that a script file's commits are unseen; named in the `check_shared_clone_commit`
  docstring and the change note's Watch. Ruled by the orchestrating lane session (fix/gate-heredoc-body), 2026-11-26,
  from the branch-wide review's ask.
