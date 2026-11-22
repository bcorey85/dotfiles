---
type: "Change"
change_type: "added"
title: "Deny a docker run without --name and print the fixed form"
description: "git-discipline-gate denies a Bash command whose docker run, docker container run or podman run step carries no --name, and prints the step as it is to be run: the same words with --rm --name <ticket>-<purpose> inserted after run, <ticket> filled from the branch's leading KEY-123 when it has one. docker compose run and docker exec pass. The hook's median time on a matched call equals its time on an unmatched one."
generated: {"by": "claude-code/claude-fable-5-1", "at": "2026-11-22T12:59:20-06:00"}
seq: 5
kind: "fix"
components: ["script/git-discipline-gate", "script/docker-run-names", "script/shell-command", "script/shell-command-words", "script/directory-emptying-deletes", "script/plan-format"]
evidence: ["queue item ad-hoc-docker-run-leaves-unnamed-unowned: a session ran a one-off docker run without --name or --rm, the process hung and the randomly named container ran for days with nothing tying it to a ticket or session"]
watches: []
test: "tests/scripts/test_git_discipline_gate.py::UnnamedDockerRunGateTest::test_an_unnamed_run_is_denied_with_the_fixed_form"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `lib/docker_run_names.py`, the owner of whether a `docker run` names its container and of the fixed form: `unnamed_docker_runs(command, directory)`. Each simple command is placed through `lib/shell_steps.py` `placed_commands` with containers kept, so wrappers such as `timeout 60` stay in the fixed form; a step is a target when its command word is `docker` or `podman` and its subcommand is `run` or `container run`. The image is found by `lib/shell_command.py` `container_run`, which skips option values through `DOCKER_VALUE_OPTIONS` with `clusters_take_values`; a `--name <value>` or `--name=<value>` before the image makes the step pass. The fixed form inserts `--rm --name <ticket>-<purpose>` after `run` (`--rm` only when the step has none), `<ticket>` from the branch's leading ticket key read through `lib/plan_format.py` `TICKET_KEY`, else the literal `<ticket>`; `<purpose>` stays literal.
- `gates/git_discipline_gate.py` rule 10 raises `DenyError` opening `[git-discipline-gate] docker run without --name`, says that an unnamed container cannot be tied to a ticket or session, then `Run it as: <fixed form>`, and that `--name` carries the ticket number and `--rm` removes the container at exit.
- Known limits, in the module docstring, no code: a global value option missing from `DOCKER_VALUE_OPTIONS` skips the whole call; a `run` value option missing from it has its value read as the image; a trailing `&` is left off the fixed form; a run inside backticks or a double-quoted `$( ... )` is never read.
- The module docstring names it the owner of its fact (`claude/.claude/scripts/CLAUDE.md` gets no Owners line for it, and the `directory_emptying_deletes` Owners line and `placed_commands` clause of the earlier change come out: a CLAUDE.md edit needs the user's own yes); the module in both lib lists of `docs/toolkit-script-rules.md`.

## Evidence

Queue item ad-hoc-docker-run-leaves-unnamed-unowned: a session hand-rolled a one-off `docker run` without `--name` or `--rm` for a compile check; Docker picked a random name, the process hung and the container ran for days with nothing tying it to a ticket or session.

Hook time, 30 runs each, payload cwd this worktree (branch `fix/gates-nov22`, no ticket key), measured under a load average of 15 while a review ran: bare `python3 -c pass` 10 ms median; the gate on a matched `docker run image cmd` 76 ms median; the gate on an unmatched `docker run --name x image cmd` 74 ms median; the gate on an unmatched `git status` 74 ms median. The rule adds no measurable time on a matched or an unmatched call; the gate's own start under this load is about twice its idle figure of 37 ms recorded in seq 4.

## Result

`docker run image` is denied with `Run it as: docker run --rm --name <ticket>-<purpose> image`; `timeout 60 docker run image` keeps its wrapper in the fixed form; `docker run --name x image`, `docker compose run web pytest` and `docker exec c cmd` pass.

## Watch

No registered watch. The next hook census counts git-discipline-gate denials whose reason opens with `docker run without --name`, and how many are followed by the printed fixed form rather than a reworded run.

## Back-out

Revert the commit. `settings.json` is unchanged, so no hook entry moves.
