---
type: "Change"
title: "The metrics writers run only while the telemetry switch is on"
description: "Every metrics writer checks one helper first. The switch is on when CLAUDE_TOOLKIT_TELEMETRY=1 is set or the file ~/.claude/toolkit-telemetry exists. Off, each writer skips its write and exits 0."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-20T23:22:51-05:00"}
seq: 15
components: ["script/telemetry-switch"]
evidence: ["tests", "judgment"]
watches: []
---

## Change

- New helpers `scripts/telemetry_enabled.sh` and `scripts/telemetry_enabled.py`. Each exits 0 when the switch is on and 1 when it is off. A missing helper counts as off and never breaks a hook.
- The switch is on when `CLAUDE_TOOLKIT_TELEMETRY=1` is set, or when the file `~/.claude/toolkit-telemetry` exists. The file check is temporary, for sessions that started before the export.
- These writers check the helper before they write: `log-agent-usage` (.py and .sh), `log-skill-use` (.py and .sh), `test-edit-telemetry` (.py and .sh), `coder-gate.py` (its log row only, denies are unchanged), `log-escape` (prints one line when off), `log-scan`, `log-spec-run`, `log-review-metrics`, `log-perf-finding`, `log-review-finding` (explicit `out=` only), the `review-scope` caller line, and the receipt line in `skills/branch-recap/SKILL.md`.
- Never gated: `review-findings.jsonl` (the deferred queue), the code-step `reports.jsonl`, hunk comments, the security gates. Blocks, prints and `finding_id=` output run as before.
- `log-escape` and `log-review-finding` take `--check` as the first argument. It runs the logger's own validation, writes nothing and ignores the switch.

## Evidence

Tests: a switch test file covers each writer with the switch on, off, and the helper deleted. The four Python writers fall back to off on an `ImportError`. The per-writer test files and the patched review-fix and stage tests pass against the installed paths.

Judgment: metrics rows from this machine's own toolkit work do not belong in the work-log counts. One switch lets a machine stop writing them.

## Result

Installed 2026-10-20. The switch file exists on this machine, so the writers stay on here until the file is deleted. A machine without the switch file or the variable writes no metric rows, so its edit watches stay flat.

## Watch

None. This change turns metric rows off or on and does not change agent behavior. Any edit watch reads flat on a machine with the switch off.

## Back-out

Reinstall the previous writers from the dotfiles history and delete the two helper scripts.
