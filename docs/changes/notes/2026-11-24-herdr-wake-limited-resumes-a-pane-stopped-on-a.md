---
type: "Change"
change_type: "added"
title: "herdr-wake-limited resumes a pane stopped on a usage-limit or overload API error"
description: "A herdr Claude pane whose transcript ends on a usage-limit or server API error gets one resume prompt once the reset time has passed, read through a shared API-error reader that lane-status now uses too."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T23:52:41-06:00"}
seq: 7
kind: "fix"
components: ["script/herdr-wake-limited", "script/lane-status", "script/session-pane", "script/script-utils", "script/loop-transcript"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_herdr_wake_limited.py::HerdrWakeLimitedTest::test_a_pane_past_its_usage_limit_reset_gets_one_resume_prompt"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`claude/.claude/scripts/lib/api_error_stop.py` (new) owns the error kind (`error_reason`: login versus other errors, told by an
`authentication_failed` error kind or by login words in the text parts; the message id is not read, so one holding
`401` no longer reads as a login) and `resume_epoch` (usage limit: `resetsAt` + 60 s; server error: record time + 300 s;
login, billing and bad-request errors: none; none for an error whose resume time passed more than a day ago).
`herdr_agents.herdr_agent_transcript` finds a herdr agent's transcript
and `script_utils.last_api_error` reads its last user or assistant record when it is an API error, skipping system,
last-prompt and cost records written after it. `script_utils.ends_on_api_error` now goes through `last_api_error`, so
the review loop's dead-subagent read (`loop_transcript.agent_died`) also skips non-conversation records after the
error: a subagent whose API error is followed by a `system` record now counts as died. `lane_status.py` drops its own
transcript lookup, error read and `LOGIN_WORDS` and uses these three, so a lane whose API error is followed by a
non-conversation record now reads dead too. `herdr_agents.herdr_reply` now gives up after 20 s, so lane-status and
session-pane report a hung herdr-api as a failed call. `scripts/.local/bin/herdr-wake-limited` sends one
`herdr-api agent prompt` to an idle or done Claude pane whose last user or assistant record is such an error once its
resume time passed, keeps the error record uuids it resumed in `herdr-wake-limited.resumed` so no error is resumed
twice, skips panes it handled on screen or whose screen read failed, and sends no resume prompt under tuios. `install/herdr-wake-limited` names the new step in its header.

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
