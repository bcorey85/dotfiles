---
type: "Change"
title: "Coder guard refuses whole-suite make and docker checks"
description: "The coder bash guard reads a make target's Makefile text and the command inside a docker exec or run call, and refuses the call when it runs a whole test suite, lint or build."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-24T16:11:34-05:00"}
seq: 14
kind: "behavior"
components: ["script/coder-gate"]
evidence: ["census"]
watches: ["coder-guard-make-check-seconds", "coder-guard-make-review-findings"]
test: ""
unmeasured: ""
overlap: "coder-gate-lint-changed-files, test-sibling-whole-suite: the watch coder-guard-make-review-findings reads review findings per code-reviewer run. coder-gate-lint-changed-files reads all of those findings too and expects the reading to fall. test-sibling-whole-suite reads only the test-gap and weak-assertion findings among them and expects those flat, so a change in them is read against all three edits."
---

## Change

The coder bash guard judges `make <target>` by the recipe commands it reaches: prerequisites, `$(MAKE) x` recursion
(depth 5), simple variables, `-C`, `-f`. It judges `docker compose exec|run`, `docker-compose` and `docker exec|run`
by the command inside the container. A call whose recipe or inner command runs a whole test suite, lint or build is
refused, and the refusal names the target and the recipe command and says to run the targeted command directly on the
changed files; `coder_gate.py set` prints the same target and recipe line under each refused command. A make call with
a `NAME=value` argument, with no Makefile or with a missing target goes through, and so does a docker call that
forwards a `NAME=value` set before it (`-e NAME`, `--env NAME`) to an inner make, and a docker call that sets a variable
itself (`-e NAME=value`) goes through the same way. Order-only prerequisites are followed. A make call with `-n`, `-q`,
`-t`, `-h` or their long forms runs no recipe line except one marked `+` or one that names `$(MAKE)`, which is not judged; the call is not judged.
`-p` still runs the recipes and is judged like the same call without it. An `include`, `export`, `unexport` or `vpath`
line and a `define` block do not end the rule above them.

## Evidence

census

## Result

Coders on work repos spend much of their check time in `make` targets; before this change the guard saw only the
literal `make test` and let it run the whole suite. Effect unmeasured until the watches read: coder check seconds per
dispatch should fall and review findings per code-reviewer run should not rise.

## Watch

`coder-guard-make-check-seconds` and `coder-guard-make-review-findings`.

## Back-out

Restore `claude/.claude/scripts/code/coder_gate.py` and `tests/scripts/test_coder_gate.py` from git (its new tests call
`command_check_scope`, `whole_package_reason` and the `set` and `bash-hook` verbs);
`claude/.claude/scripts/lib/makefile_text.py` and the `unwrap_docker`, `without_assignments`,
`docker_forwarded_variables` and `docker_set_variables` functions in `claude/.claude/scripts/lib/shell_command.py` can
stay unused once `coder_gate.py` is restored (it is their only caller), and so can the staging edits in
`tests/scripts/test_code_step.py`, `tests/scripts/test_code_step_termination.py` and
`tests/scripts/test_telemetry_switch.py`.
