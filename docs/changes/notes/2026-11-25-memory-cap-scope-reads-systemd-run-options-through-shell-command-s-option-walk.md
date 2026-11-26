---
type: "Change"
change_type: "fixed"
title: "memory_cap_scope reads systemd-run options through shell_command's option walk"
description: "shell_command.command_options walks any command's options into (option, value) pairs, git_options is its git form, and memory_cap_scope reads the systemd-run options and slice through it with no loop of its own."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-25T17:27:51-06:00"}
seq: 6
kind: "fix"
components: ["script/memory-cap-scope", "script/shell-command"]
evidence: ["tests/scripts/test_shell_command.py", "tests/scripts/test_memory_cap_scope.py"]
watches: []
test: "tests/scripts/test_shell_command.py::CommandOptionsTest::test_value_options_in_both_forms_and_a_quoted_value_are_read_and_the_program_follows"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`lib/shell_command.py` gains `command_options(words, value_options)`, which returns the (option, value) pairs of a command's options and the index after them. `git_options(words)` is now `command_options(words, GIT_VALUE_OPTIONS)`, and `option_values` reads any such pair list. `memory_cap_scope.systemd_run_slice` returns the last `--slice` value from that pair list, and `systemd_run_options_end` returns the index it gives. The option loop in `systemd_run_slice` is gone. `command_options` does not read short clusters such as `-iC dir`; its docstring sends a caller that needs that, and only the index, to `skip_options(..., clusters_take_values=True)`.

## Evidence

`command_options` on a systemd-run word list with `--slice x`, `--slice=y` and `-p "X=$(cmd)"` pairs each value and ends at the program. The memory_cap_scope tests and the git_options callers' tests pass unchanged.

## Result

One option walk serves git and systemd-run, so the two no longer repeat it. Two edges differ from the old systemd-run skip. A `--slice=X` word that is the value of an earlier value option other than `--slice` (`systemd-run -p --slice=x cmd`) used to read as the slice `x` and now reads as None. A `--slice=y` word that is the value of an earlier `--slice` (`systemd-run --slice --slice=y cmd`) used to read as `y` and now reads as `--slice=y`, the value systemd-run's own parsing gives. A value option as the last word changes only the internal index, not any output.

## Watch

A systemd-run step whose slice is read as None when it names one: its option is missing from `SYSTEMD_RUN_VALUE_OPTIONS`.

## Back-out

Revert the Phase 5 commit of one-owner-nov25.
