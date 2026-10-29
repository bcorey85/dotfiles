---
type: "Change"
change_type: "fixed"
title: "Telemetry scripts find the ledger in the cargo bin folder and warn when it is missing"
description: "The telemetry writers and readers now also look for `ledger` in ${CARGO_HOME:-~/.cargo}/bin; the settings.json hooks run a new `ledger-hook` wrapper. The /review and /code reports say so when no ledger is found. The fallback stays: no hard error. Before, they looked on PATH only, so a hook or Bash call without the login PATH missed the installed ledger and wrote rows to the jsonl fallback, which the ledger's readers never see."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T13:27:33-05:00"}
seq: 109
kind: "fix"
components: ["script/ledger-write", "script/review-fix", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_ledger_write.py::LedgerWriteTest::test_a_ledger_in_the_cargo_bin_folder_gets_the_row_when_path_has_none"
asked: "no hard error (Brandon, 2026-10-27)"
proof: []
unmeasured: ""
---

## Change

- New `scripts/lib/_ledger.sh` (`ledger_bin`) and `script_utils.ledger_bin()`: the first `ledger` on PATH, else
  `${CARGO_HOME:-$HOME/.cargo}/bin/ledger`. `ledger-write`, `read_ledger` and claude-doctor use it.
- New `scripts/telemetry/ledger-hook <event>`: runs `ledger hook <event>` through `ledger_bin` and always exits 0. It
  replaces the inline `command -v ledger && ledger hook <event>` in the nine settings.json telemetry hooks.
- `script_utils.missing_ledger_warning()`: with telemetry on and no ledger, the /review report gets a Ledger section
  and the /code phase close says the same line. With telemetry off, or a ledger found, nothing is shown.
- The test runner gives every test process an empty CARGO_HOME, so a test that hides the ledger from PATH never
  reaches the ledger installed on the machine.

## Evidence

- The ticket's first criterion asked for a resolvable ledger and "a missing ledger is a loud error, not a silent
  fallback". Brandon narrowed it on 2026-10-27: "no hard error". Earlier the same day: "my claude skills can never
  have a hard dependency on ledger". So the fallback stays and is made loud in the user's report instead.
- The ticket's second criterion (every finding a round raises gets one ledger row) is already met on master: the
  stop hook counts finding rows per finding, and the scripted review loop logs every finding in code.
- The ledger installs to `~/.cargo/bin` through `cargo install`; the work intake reports "ledger not installed"
  while the user's login shell finds it.
- The new tests fail before the change: with the ledger only in the cargo folder, ledger-write appended to the jsonl
  file and the report carried no warning.

## Result

- Changed test files pass (ledger_write, script_utils, review_fix_script, telemetry_switch, log_review_metrics,
  log_spec_run, toolkit_self_location, verify_common_review_ran, review_loop_gate, ledger_hook, code_step). Ruff is clean.
- The user applied the settings.json edit by hand, since a hook blocks agents from editing it.
- The audit skill files still call `ledger` from the model's shell; they are out of this change.

## Watch

—

## Back-out

Revert both commits: the scripts and the settings.json hook swap.
