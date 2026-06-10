---
name: msg
description: Send a message to another Claude agent running in a separate repo's tmux session. Works for questions or statements. The message lands in that repo's inbox buffer; the other agent reads it with /inbox.
argument-hint: "<recipient-repo> <message...>"
allowed-tools: Bash(claude-msg send:*)
---

Run this command:

```
claude-msg send $ARGUMENTS
```

The first token in `$ARGUMENTS` is the recipient repo handle (e.g. `jarvis`, `narrative-engine`). Everything after is the message body — a question, a statement, an FYI, whatever. The message is appended to that repo's tmux inbox buffer (`claude_inbox_<recipient>`).

Tell the user the message was delivered and that they should have the other agent run `/inbox` (or `claude-msg read`) to fetch and act on it.
