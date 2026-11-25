---
type: "Change"
change_type: "added"
title: "herdr-wake-limited resumes a pane stopped on a usage-limit or overload API error"
description: "A herdr Claude pane whose transcript ends on a usage-limit or server API error gets one resume prompt once the reset time has passed, read through a shared API-error reader that lane-status now uses too."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T23:52:41-06:00"}
seq: 7
kind: "fix"
components: ["script/herdr-wake-limited", "script/lane-status"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_herdr_wake_limited.py::HerdrWakeLimitedTest::test_a_pane_past_its_usage_limit_reset_gets_one_resume_prompt"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`claude/.claude/scripts/lib/api_error_stop.py` (new) owns the read of a session's last API error: the transcript of a
herdr agent, the last record when it is an API error, login versus other errors (from the message text only, so a
message id holding `401` no longer reads as a login), and `resume_epoch` (usage limit: `resetsAt` + 60 s; server
error: record time + 300 s; login, billing and bad-request errors: none). `lane_status.py` drops its own copy and
imports it. `scripts/.local/bin/herdr-wake-limited` sends one `herdr-api agent prompt` to an idle or done Claude pane
whose last record is such an error once its resume time passed, keeps the error record uuids it resumed in
`herdr-wake-limited.resumed` so no error is resumed twice, skips panes it already handled on screen, and does nothing
under tuios. `install/herdr-wake-limited` names the new step in its header.

## Evidence

Judgment, plus a sweep of the local transcripts: 244 of 244 `rate_limit` records and 6 of 6 `server_error` records get
a resume time; no authentication, billing, bad-request or org error does.

## Result

The waker tests cover one prompt per error, a second run, a future reset, a normal last turn, login and billing errors,
a working pane, a pane at the reset prompt, tuios, a failed prompt retried, and a new error after a resume.

## Watch

None: run `systemctl --user list-timers` after the install and read `herdr-wake-limited.log` for `resumed` lines.

## Back-out

Revert the commit; delete `~/.local/state/herdr-wake-limited.resumed`.
