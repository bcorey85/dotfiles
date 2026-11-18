---
type: "Change"
change_type: "fixed"
title: "code-wait agent prints only a report no earlier wait printed"
description: "`code_wait.py agent` records each report it prints and prints a report again only when the agent wrote a newer one, so a wait on a resumed agent no longer returns its last phase's report."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-18T00:17:26-06:00"}
seq: 1
kind: "fix"
components: ["script/code-wait", "script/loop-transcript", "script/script-utils"]
evidence: ["code-wait-returns-stale-phase-report"]
watches: []
test: "tests/scripts/test_code_wait.py::WaitAgentTest::test_a_second_wait_does_not_print_the_report_an_earlier_wait_printed"
asked: ""
proof: []
unmeasured: "One sentence added to skills/code/SKILL.md and _shared/review-fork-run.md: after an already-printed report with no SendMessage since, read the named transcript instead of waiting again. No rule-meter run: it follows a line the script prints."
---

## Change

`code_wait.py agent` writes the report it printed (agent id, transcript line, time) to
`~/.claude/state/agent-reports/<agent id>.json`, keyed by agent id so the wait's cwd does not matter. A later wait prints a report only when its transcript line is
after the recorded one. `LoopTranscript` gained `last_text_line`. When the only report is the one already printed and
the wait times out, it prints `STILL_WORKING` and a line that names the earlier print and the transcript path.

## Evidence

A resumed agent still holds its first delivered hand-back, so the first wait after a SendMessage resume printed the
old report. On this machine, the resume row reaches the child transcript 0.1 s to 367 s after SendMessage returns, so
the transcript alone cannot tell the two apart.

## Result

Eight new tests in `tests/scripts/test_code_wait.py`, among them a second hand-back after a resume row and a resume row
with no new hand-back. `bash tests/run.sh`: 4657 tests, 0 failed.

## Watch

None.

## Back-out

Revert the commit and delete `~/.claude/state/agent-reports/`.
