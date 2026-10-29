---
type: "Change"
change_type: "fixed"
title: "Telemetry loggers print their usage on --help instead of refusing it as a malformed argument"
description: "`log-escape --help` and `log-spec-run --help` refused the flag as a malformed key=value pair, so the four loggers and log-escape-check in telemetry/, and the four review scripts, now print their header usage block on --help or -h, exit 0 and write no row."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:40:14-05:00"}
seq: 91
kind: "fix"
components: ["script/log-escape", "script/log-spec-run", "script/log-scan", "script/log-escape-check", "script/ledger-write", "script/log-review-finding", "script/log-review-metrics", "script/log-review-check", "script/review-scope"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_log_escape.py::LogEscapeTest::test_help_prints_usage_and_writes_nothing"
asked: ""
proof: []
unmeasured: ""
---

## Change

`scripts/lib/_kv.sh`:

- New `kv_help_exit <script_path> "$@"`. When the first argument is `--help` or `-h`, it prints the script's leading
  comment block and exits 0. Any other first argument changes nothing.

`scripts/telemetry/`:

- The four loggers (`log-escape`, `log-spec-run`, `log-scan`, `ledger-write`) and the no-model check
  `log-escape-check`, which writes no row, call it before any parsing, tool check, ledger call or temp dir. `ledger-write` and `log-escape-check` now source `_kv.sh`; the other three did already.
- The four review scripts in `skills/review/` (`log-review-finding`, `log-review-metrics`, `log-review-check`,
  `review-scope`) call it the same way. `log-review-check` and `review-scope` now source `_kv.sh`; the other two did
  already. `log-review-check` prints its usage before it makes its temp dir.
- `log-spec-run`'s and `log-review-metrics`'s jq checks moved below the help call, so `--help` works without jq on both.
- Not changed: `log_agent_usage.py`, `log_skill_use.py` and `test_edit_telemetry.py` are stdin hooks with no
  arguments, and `telemetry_enabled.sh` and `telemetry_enabled.py` are switch probes with no arguments.

Tests: one `--help`/`-h` case per logger in `tests/scripts/` (`test_log_escape.py`, `test_log_scan.py`,
`test_log_spec_run.py`, `test_ledger_write.py`), one for both check scripts in the new `test_log_escape_check.py`
(`log-escape-check` and `log-review-check`), and one each for `log-review-finding`, `log-review-metrics` and
`review-scope` (`test_log_review_finding.py`, `test_log_review_metrics.py`, `test_review_scope.py`). Each checks exit 0,
the usage text on stdout, empty stderr and no row written, except review-scope's test, which checks exit 0, usage on
stdout and empty stderr only. All the subtests fail against the scripts before this change.

## Evidence

- Two reports from agent-ledger sessions on 2026-10-26: `log-escape --help` and `log-spec-run --help` printed
  "skipping malformed arg" and "refusing to log", so the session read the script source to learn the fields.
- The toolkit tells every session to check a command with `--help` before guessing it, so the refusal fires on every
  such check.

## Result

A session that runs `--help` on a telemetry logger gets its usage text and no row.

## Watch

None. The intake does not count logger refusals by cause.

## Back-out

Remove `kv_help_exit` from `scripts/lib/_kv.sh` and its call line from each of the four loggers, `log-escape-check` and the four review scripts, and drop the help
tests.
