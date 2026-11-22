# Acceptance criteria

- **AC1** — A Bash command whose plain `rm` targets cover every entry of an existing directory outside a temp or build folder is denied by git-discipline-gate with text that names the directory and the recursive form; an `rm` that leaves an entry behind passes. (Phase 1)
- **AC2** — The cross-call shape is caught: after `rm d/a` has run, `rm d/b` on the now one-file directory is denied. (Phase 1)
- **AC3** — A `docker run` (or `docker container run`) step with no `--name` is denied with text that gives the fixed form carrying `--rm --name <ticket>-<purpose>`; a run with `--name` passes; `docker compose run` and `docker exec` pass. (Phase 2)
- **AC4** — No new hook process: both rules live in `gates/git_discipline_gate.py`, `settings.json` is unchanged, and `bash-safety-gate.sh` is unchanged. (Phase 1, Phase 2)
- **AC5** — `bash tests/run.sh` passes and `bash tests/lint.sh` passes on every changed `.py` file.
