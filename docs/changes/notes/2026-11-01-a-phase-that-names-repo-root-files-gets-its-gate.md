---
type: "Change"
change_type: "fixed"
title: "A phase that names repo-root files gets its gate"
description: "A plan phase or no-plan hand-off that names only repo-root files such as `app.py` now gets the same lint and test gate as one that names nested files."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T01:54:00-06:00"}
seq: 429
kind: "fix"
components: ["script/plan-format", "script/gate-commands", "script/coder-packet", "script/expected-red"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_gate_commands.py::RootFilesTest::test_a_phase_that_names_repo_root_files_gets_the_gate_a_nested_phase_gets"
asked: ""
proof: []
unmeasured: "A fix with a failing-before test; no intake number counts phases gated with no command."
---

## Change

`plan_format.PATH_IN_BACKTICKS` takes a path with no folder and a `+` in a segment (`src/routes/+page.svelte`). The new `plan_format.named_paths` keeps a bare `name.ext` only when the repo root holds that file, so prose such as `os.path` or `row.ts` adds no command. `gate_commands`, `coder_packet` and the no-plan hand-off path read through it. A `**File**:` entry counts a bare name with no check, so later-phase files include root files. The root `Cargo.toml` special case is gone: `named_paths` covers it.

## Evidence

judgment: a bug hunt showed `derive_gate_commands` return `[]` for a phase naming `app.py` and `test_app.py`, while the nested twin got ruff and pytest. The coder gate then passed with no command run.

## Result

The root phase gets `ruff check {files:.py}` and `python3 -m pytest test_app.py`.

## Watch

—

## Back-out

Revert the commit.
