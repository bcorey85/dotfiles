---
name: inbox
description: Fetch and consume pending messages sent by other Claude agents via /ask. Pass a repo handle to read another repo's inbox; omit to read the current repo's inbox.
argument-hint: "[recipient-repo]"
allowed-tools: Bash(claude-msg read:*), Bash(claude-msg peek:*)
---

Run the appropriate command based on context:

- To read and consume messages (default): `claude-msg read $ARGUMENTS`
- To peek without consuming: `claude-msg peek $ARGUMENTS`

When `$ARGUMENTS` is empty, both commands default to `basename $PWD` as the inbox target.

After fetching the messages, act on them: answer any questions, produce requested output, or note if the inbox was empty. If the user only wants to inspect without clearing, use `claude-msg peek` instead.
