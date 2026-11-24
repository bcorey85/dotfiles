---
type: "Change"
change_type: "fixed"
title: "Lane sessions start with the cron scheduler off so a fork drops the parent's timers"
description: "herdr-dev starts every forked or resumed lane session with CLAUDE_CODE_DISABLE_CRON=1, so a lane no longer restores and fires the orchestrator's cron jobs."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T04:26:18-06:00"}
seq: 1
kind: "fix"
components: ["script/herdr-worktree", "script/herdr-dev", "script/herdr-worktree-watch"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_herdr_dev.py::HerdrDevTest::test_positional_form_still_forks"
asked: ""
proof: []
unmeasured: "A fix with a failing-before test and a scripted fork run; no intake number counts timer fires in lanes."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`herdr-dev` types `CLAUDE_CODE_DISABLE_CRON=1 claude --resume <id> ...` for every session start, fork and `--resume` alike. A start with no session still types plain `claude`. The watcher's fallback step names the same variable. Lanes cannot call CronCreate.

## Evidence

judgment: Claude Code 2.1.331 keeps a session's cron jobs in its transcript as `session_cron_carry` attachments, and `--resume <id> --fork-session` restores them. A lane forked from agent-evals-73 fired its night-check timer 9 times during a usage limit. A scripted fork of a probe session with one cron job: the plain fork's CronList showed the parent job; with `CLAUDE_CODE_DISABLE_CRON=1` CronList was unavailable and no job ran. A later resume of that fork without the variable restored the job, so lane resumes through `herdr-dev --resume` set it too.

## Result

A forked lane holds no cron job at start. Suite: 6251 tests, 0 failed.

## Watch

—

## Back-out

Revert the commit.
