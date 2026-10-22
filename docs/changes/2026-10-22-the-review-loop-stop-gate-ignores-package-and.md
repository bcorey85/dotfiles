---
type: "Change"
title: "The review-loop stop gate ignores package and project flag values when it judges a scoped run"
description: "review-loop-gate.py no longer reads the value of a package, project or manifest flag as a test filter, so `cargo test -p core` counts as a full gate run. The script also carries a hand-back check that is not registered in settings.json."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-22T09:53:16-05:00"}
seq: 11
components: ["script/review-loop-gate", "script/script-utils"]
evidence: ["transcript read"]
watches: []
---

## Change

- `scripts/script_utils.py`: new `strip_flag_values(command, flags)`. It removes each `flag value` and `flag=value` pair of the named flags.
- `scripts/review-loop-gate.py`, gate-run check:
  - `NON_SCOPING_FLAGS` names, for each checker, the flags whose value picks a package, a project or a manifest. cargo: `--manifest-path`, `-p`, `--package`. pytest, go, mypy, pyright: `-p`. tsc: `-p`, `--project`. vitest, dotnet: `--project`.
  - The scope check removes those values before it looks for a file, folder or test-name filter. The checker comes from a named group in `CHECKER`.
  - A flag of another checker still scopes a run. For example, `rspec -p spec/a_spec.rb` and `bats -p x.bats` select a test file.
  - `--workspace` is not stripped.
- `scripts/review-loop-gate.py`, hand-back check, dormant: a `PreToolUse` branch for `SubagentHandback` refuses a review loop's first hand-back while a stop check would block, and a second hand-back goes through. settings.json has no entry for it, so it does not run.
- Tests: `test_review_loop_gate.py` and `test_script_utils.py` under `tests/scripts/`.

## Evidence

- Transcript read: the gate read a full run, `cargo test --manifest-path /abs/Cargo.toml`, as scoped because the path read as a filter, so it blocked for a missing full check. The other package and project flags have the same shape. Most stop-gate blocks fired after the hand-back, so they changed nothing and the loop still ended. The dormant hand-back check is for those.

## Result

A whole-package gate run with a package or project flag counts as the full run. Gaps that predate this change: `cargo test parser`, `pytest tests` and `npm test --workspace=packages/web` still read as full runs, and Playwright is not a known checker.

## Watch

None. The intake counts stop-gate blocks only in a weekly total that the edit watch does not read.

## Back-out

Restore the previous `review-loop-gate.py` from git. `strip_flag_values` can stay.
