---
type: "Change"
title: "Global Safety Rails: when a hook blocks a shell write and tells the agent to use Write or Edit"
description: "Global Safety Rails: when a hook blocks a shell write and tells the agent to use Write or Edit, the agent does that and continues."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-02T00:00:00-05:00"}
seq: 11
components: ["rule/global-claude-md"]
evidence: ["judgment"]
watches: []
---

## Change

Global Safety Rails: when a hook blocks a shell write and tells the agent to use Write or Edit, the agent does that and continues. Every other block still means report and stop, with no rephrase and no skip comment without the user's say-so

## Evidence

judgment

## Result

In one bench ticket run, 9 of 15 coder dispatches hit the shell write gate. 8 redid the write with Edit and kept going. 1 followed the stop rule, and its phase ended with no review. Work logs cannot size it, because the shell write gate does not log its blocks. 15 more words on every main-session and subagent request. Untested under the rule. Check after the edit: subagent runs that end right after a block, in the work logs.

## Watch

—

## Back-out

restore the sentence from git
