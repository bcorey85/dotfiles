---
type: "Change"
change_type: "fixed"
title: "full_check base run sees a repo given by its symlinked path"
description: "full_check's base run and linked_installs match a repo by both its given path and its resolved path, so a repo under a symlinked folder (macOS /var) still skips the base run when the command, env or an editable install names it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-03T09:05:51-06:00"}
seq: 3
kind: "fix"
components: ["script/full-check", "script/linked-installs"]
evidence: ["macOS suite run"]
watches: []
test: "tests/scripts/test_full_check.py::BaseComparisonTest::test_a_base_run_is_skipped_only_when_the_command_or_env_names_the_repo_path_itself"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/full_check.py` `base_run` builds `repo_spellings` from the resolved and the given (absolute, unresolved) repo path and passes them to `base_run_would_test_head`, which checks the command, `gate_env` values and editable installs against each spelling. `lib/linked_installs.py` `holds_editable_install` takes `repo_spellings`, resolves the repo itself, and resolves a dist-info `direct_url` before `is_relative_to`.

## Evidence

On macOS a tempdir is `/var/...`, which resolves to `/private/var/...`. A command naming the given path did not match the resolved repo path, so the base run went ahead where it should have been skipped; BaseComparisonTest cases failed on Darwin 23.

## Result

Before: the base-run skip missed a repo named by its symlinked spelling. After: either spelling matches; BaseComparisonTest and LinkedInstallsTest pass on macOS.

## Watch

None: the test above pins it on a macOS run of `bash tests/run.sh`.

## Back-out

Revert the commit.

