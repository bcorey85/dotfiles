---
type: "Change"
change_type: "fixed"
title: "gate commands use folder flags in place of cd chains"
description: "No gate command from gate_commands.py holds cd or &&: package commands use pnpm -C, npm --prefix or yarn --cwd, cargo uses --manifest-path, and a diff of only non-Rust files under a crate gives no cargo command."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T06:39:45-06:00"}
seq: 8
kind: "fix"
components: ["script/gate-commands", "script/coder-gate", "script/check-scope"]
evidence: ["gate-commands-emits-cd-and-chain-commands", "review-loop-runs-bare-cargo-test-on-a-non-rust"]
watches: []
test: "tests/scripts/test_gate_commands.py::FolderFlagCommandsTest::test_no_derived_command_changes_directory_or_chains"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code/gate_commands.py` builds package and cargo commands with the manager's folder flag, and `{files}` still
resolves. An npm package in a subfolder gets no binary command, only its package scripts. `lib/check_scope.py` reads
the folder flags. A diff whose files under a crate are all non-Rust gives no cargo command; that already held, and a
test now pins it.

## Evidence

Gate commands of the form `cd <dir> && ...` were blocked by the shell hooks and broke the check scope reader.

## Result

FolderFlagCommandsTest, PackageBinaryCommandTest and RootBinaryCommandsTest in `test_gate_commands.py`; new tests in
`test_coder_gate.py`.

## Watch

None.

## Back-out

Revert the commit.
