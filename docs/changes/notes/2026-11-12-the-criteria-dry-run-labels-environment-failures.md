---
type: "Change"
change_type: "fixed"
title: "The criteria dry run labels environment failures ENV and judges escaped rg patterns the same"
description: "A failing item whose output shows the tool could not start reads ENV with a flag, and a search ban is judged on the line's wording outside every backticked span."
generated: {"by": "process:coder", "at": "2026-11-12T00:32:08-06:00"}
seq: 2
kind: "fix"
components: ["script/criteria-verdict", "script/criteria-dry-run"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_criteria_verdict.py::ItemVerdictTest::test_an_environment_failure_reads_env_and_keeps_the_exit_style_code"
asked: ""
proof: []
unmeasured: ""
---

## Change

`criteria_verdict.item_verdict` reads outcome `ENV`, keeping the exit-style code, when the command failed, no test failed, and its output
matches `check_output.RUNNER_CANNOT_START` (uv `Failed to spawn:`, poetry `Command not found:`, pipenv `could not be
found within PATH`, with its `Error: ` prefix read in any case) or `SHELL_OR_SHIM_CANNOT_START` (a line-anchored top-level shell
`command not found`, sh `not found`, mise `Tool not installed for shim`, `Failed to install`, `not currently active`
or `No version is set`, pyenv version not installed, asdf `No version is set` or `No preset version installed`). The dry run's own
`/bin/sh: line N: <tool>: command not found` reads ENV. Any other `: line N:` form, from a repo script or
`bash: line N:`, reads RED. The mise forms are captured from mise 2026.11.3; the asdf and pyenv forms are not
captured on this machine. A run whose output has a failing-test summary or failing-test lines never reads ENV, so a
unittest `FAILED (failures=1)` or a quoted `Failed to spawn:` inside a failing run stays RED. `is_search_ban`, the presence-wording note check and `criteria_dry_run.stated_count`
judge the line with every backticked span removed instead of `line.replace(command, "")`. `item_verdict` sets the flag
`environment failure: <the matched output line>` for ENV and the dry run prints it (not the last output line, which is mise's `Run with --verbose` boilerplate), which needs an answer like BROKEN.

## Evidence

judgment: a version-manager shim failing (mise's uv exiting 1 for a missing pinned version) made every uv criterion
read RED, and a no-match rg with escaped asterisks read GREEN at rc 1 while the unescaped form read RED.

## Result

The new verdict and dry-run tests fail on the old tree and pass; test_criteria_verdict, test_check_output and
test_criteria_dry_run pass.

## Watch

The ENV pattern lists forms of mise, pyenv and asdf messages; a new message form reads RED until added.

## Back-out

Revert the commit.
