---
type: "Change"
change_type: "fixed"
title: "Stale-prose and refactor scripts share the lib git runner and C-path decoder"
description: "The stale-prose merge brought back a git_output copy and a second unquote_c_path, which the duplicate check failed on; stale_prose now runs git through script_utils.run_or_raise and refactor_flow decodes quoted paths through source_text."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T19:30:00-05:00"}
seq: 11
kind: "fix"
components: ["script/script-utils", "script/source-text", "script/stale-prose", "script/refactor-flow"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_toolkit_self_location.py::ToolkitSelfLocationTest::test_every_home_lookup_of_toolkit_code_is_allowed_by_name"
asked: ""
proof: []
unmeasured: ""
---

## Change

`script_utils.run_or_raise` takes `ok_codes` and `timeout`. It decodes output as UTF-8 with no newline
translation, and a run past the timeout raises the caller's error.

`stale_prose.git_output` becomes `git_stdout`, a call to `run_or_raise`. `refactor_flow` drops its own
`unquote_c_path` and escape tables and calls `source_text.unquote_c_path`. The `source_text` docstring no longer
names a home-folder path.

Behavior that moved:

- stale_prose errors name the whole git command.
- verify and refactor git output keeps `\r` as git wrote it.

## Evidence

The full suite on master after the rebase failed: 4 duplicate-code hits and one self-location test.

## Result

`bash tests/run.sh` passes on this branch.

## Watch

None.

## Back-out

Revert the commit. The duplicate check fails again.
