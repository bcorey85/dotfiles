---
type: "Change"
title: "code-step runs env-prefixed checks, clippy for Rust phases, and commits a plan edited before the phase"
description: "code-step reads a verification command with leading NAME=value assignments and runs it with them set. A phase that touches Rust code gets a clippy gate. The phase commit includes the plan when the phase ticked it, even if the plan had edits before the phase. coder-packet no longer reads Phase 6.1 as Phase 6. One plan parser and one stage-guard table replace the duplicates."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T09:30:33-05:00"}
seq: 14
components: ["script/code-step", "script/plan-format", "script/coder-packet", "script/script-utils"]
evidence: ["work incident", "tests"]
watches: []
---

## Change

- **Env prefix:** a backticked Automated Verification command can start with `NAME=value` assignments, with plain or quoted values. The command runs with them set. An assignment with no known command after it stays unreadable and stops the phase. A whole-suite command with a prefix is still skipped.
- **Clippy:** when a phase names a `.rs` file or a `Cargo.toml`, including a bare root `Cargo.toml`, the gate adds `cargo clippy --all-targets -- -D warnings` in the nearest crate folder.
- **Plan in the commit:** the suggested commit includes the plan whenever the phase changed it. If the plan had edits before the phase, the "Files changed" text says that the commit includes them.
- **coder-packet:** it finds a phase by exact id through the shared plan parser, so `Phase 6` never matches `Phase 6.1`. It also finds `###` and `####` phase headings. A missing phase exits with a message, not a traceback.
- **Structure:** `plan_format.py` holds the one phase parser that code-step and coder-packet use. A stage-guard table replaces the guard code in each verb, with the same stop messages. `script_utils.py` holds one bounded upward file search that both scripts use. code-step.py went from 2,548 to 2,495 lines.

## Evidence

Work incidents: in one work slice, a phase's test needed an environment variable that the plan line set in front of the command. code-step ran the command without it, the test failed, and the phase stopped. With the variable set by hand, the check passed. In the same slice, the coder packet for a phase also matched a dotted sub-phase heading. A review of the code-step script found the plan-commit gap and the missing clippy gate.

A code review of the staged change found that a root `Cargo.toml` added no clippy gate. That was fixed before install. The old and new parsers gave the same result on 54,964 plan files.

## Result

Staged 2026-10-21 in the second script fix batch. 292 code-step, plan-format and coder-packet tests pass. The state-machine walk explored 564,470 paths with 0 failures. Installed 2026-10-21 with the comment-bloat change, because both scripts use the new `script_utils.py` functions.

## Watch

None. No intake metric counts phases stopped by a failed or unreadable verification command.

## Back-out

Restore the previous `code-step.py`, `plan_format.py`, `coder-packet.py`, `script_utils.py` and their tests from the dotfiles history.
