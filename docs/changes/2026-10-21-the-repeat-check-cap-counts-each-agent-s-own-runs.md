---
type: "Change"
title: "The repeat-check cap counts each agent's own runs and trusts a formatter only before a sure check"
description: "The repeat-check cap keeps a separate record for each subagent, so a reviewer or the review loop gets its own first run of a check. A formatter exempts a check only when the check surely runs after the formatter succeeds."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T08:49:36-05:00"}
seq: 13
components: ["script/quality-check-cap", "script/shell-command"]
evidence: ["transcript read", "tests"]
watches: []
---

## Change

- `scripts/quality-check-cap.py`: the run record is keyed by session and agent. A subagent's record is `run-<cksum>-<first 16 hex of sha256(agent_id)>`. The main thread keeps the bare key. The hard-coded exemption for the review loop's gate run is gone, because the loop now has its own record.
- `scripts/quality-check-cap.py`: a formatter exempts a check only when the check runs only after that formatter succeeds. `&&` chains with pipes and groups entered through `&&` count. `;`, a newline, `&`, a background list and a formatter that an earlier `||` can skip do not count. With two formatters, a check is exempt when it follows one of them.
- `scripts/shell_command.py`: new `runs_only_after_success(steps, earlier, later)`. The step splitter keeps `2>&1`, `>&2`, `&>f` and `|&` as one step and splits a lone `&` like `;`.

## Evidence

Transcript read: subagents share the parent session id, so a reviewer's or the review loop's first test run read as a repeat of the coder's run and got denied. A blocked agent stops, and the user must answer it. A code review of the staged change found that the first version of the formatter rule denied `cargo fmt && cargo clippy 2>&1 | tail -50 && cargo test`, which the installed hook allows. That and six smaller defects were fixed before install.

Trade: each new agent gets one free run of each check, even when the tree did not change since another agent ran it. A reviewer needs that run to see the test output.

## Result

Staged 2026-10-21 in the second script fix batch. 80 tests pass. Against the installed hook, 12 of the new tests fail.

## Watch

None. This hook does not write to the hook block log that the watch metrics read, so no intake metric counts its denies.

## Back-out

Restore the previous `quality-check-cap.py`, `shell_command.py` and their tests from the dotfiles history.
