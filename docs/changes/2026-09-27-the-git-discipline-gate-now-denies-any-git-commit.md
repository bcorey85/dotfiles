---
type: "Change"
title: "The git discipline gate now denies any `git commit`, `gh pr create` or `gh pr edit` command whose text"
description: "The git discipline gate now denies any `git commit`, `gh pr create` or `gh pr edit` command whose text carries `Claude-Session:`, a `claude.ai/code/session_` link or `Co-Authored-By: Claude`."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-27T00:00:00-05:00"}
seq: 9
components: ["script/git-discipline-gate", "rule/global-claude-md"]
evidence: ["judgment"]
watches: []
---

## Change

The git discipline gate now denies any `git commit`, `gh pr create` or `gh pr edit` command whose text carries `Claude-Session:`, a `claude.ai/code/session_` link or `Co-Authored-By: Claude`. The CLAUDE.md line that forbade attribution and session trailers was deleted.

## Evidence

judgment

## Result

The attribution setting already blanks the default co-author trailer. Sessions with a remote link still get a reminder to end each commit with a session link, and the reminder yields to a user rule, so the CLAUDE.md line was the only guard. The gate now enforces it for every command-line message. A message read from a file with `-F` or `--body-file` is not checked. The deleted line saves about 15 tokens on every main-session and subagent request.

## Watch

—

## Back-out

restore the line and remove the five gate lines.
