---
type: "Change"
change_type: "fixed"
title: "With no ledger the skill-use and test-edit hooks keep their rows"
description: "With no ledger and the telemetry switch on, skill-use and test-edit events now land in the jsonl files the intake copies, where they were lost before."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T22:32:29-06:00"}
seq: 463
kind: "fix"
components: ["script/ledger-hook", "script/hook-local-row"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_ledger_hook.py::test_no_ledger_keeps_a_skill_tool_call_in_the_skill_usage_file"
asked: ""
proof: []
unmeasured: ""
---

## Change

`ledger-hook` runs the new `telemetry/hook_local_row.py` when it finds no ledger, the switch is on and the event is skill-use or test-edit. Rows keep the shape of the writers removed earlier: `{ts, skill, via, repo}` in `skill-usage.jsonl` and `{ts, tool, agent, file, cwd, snippet}` in `test-edit-telemetry.jsonl`. Two things differ from those writers: the test-file check is `source_paths.is_test_path`, and `repo` comes from `script_utils.repo_name`, so a worktree logs under its repo. `claude-doctor` and the audit skill text now say where these rows go.

## Evidence

The work machine has no ledger, so with the switch on these hooks wrote nothing there. The toolkit keeps working on a missing ledger.

## Result

Median on matched calls with no ledger and the switch on: test-edit 59.0 ms, skill-use 62.9 ms, against 16.7 ms for a bare Python start. With the switch off: 7.0 ms and no Python. A machine with a ledger runs the same path as before. A new process was needed because `ledger-hook` is bash and the test-path owner is Python; it runs only on this path.

## Watch

None. The switch is off at work, so no intake number reads this until the user turns it on.

## Back-out

Revert the commit.
