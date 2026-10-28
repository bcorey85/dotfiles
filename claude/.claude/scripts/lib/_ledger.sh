#!/usr/bin/env bash
# _ledger.sh — finds the `ledger` program for the telemetry scripts and hooks. Source it; do not run it.
#
# usage: ledger=$(ledger_bin) || <no ledger>
#
# ledger_bin prints the path of the first `ledger` on PATH, else of the one `cargo install` puts in
# ${CARGO_HOME:-$HOME/.cargo}/bin, and returns 1 when neither exists. A hook or a Bash tool call can run
# without the login shell's PATH, so the cargo folder is checked by its path.
ledger_bin() {
  local on_path cargo_ledger
  if on_path=$(command -v ledger 2>/dev/null); then
    printf '%s\n' "$on_path"
    return 0
  fi

  cargo_ledger="${CARGO_HOME:-${HOME:-}/.cargo}/bin/ledger"
  # Same lookup as ledger_bin in script_utils.py.
  if [ -n "${CARGO_HOME:-}${HOME:-}" ] && [ -f "$cargo_ledger" ] && [ -x "$cargo_ledger" ]; then
    printf '%s\n' "$cargo_ledger"
    return 0
  fi
  return 1
}
