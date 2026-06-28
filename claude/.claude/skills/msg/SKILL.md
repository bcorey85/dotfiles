---
name: msg
description: "Send or receive messages between Claude agents running in separate repos' tmux sessions. Verbs — send <repo> <message>: deliver a message to another agent's inbox; read [repo]: fetch and consume the current inbox (triggers on \"check my inbox\", \"any messages\", \"what's in my inbox\"); peek [repo]: inspect without consuming; list: show all inboxes with pending mail. Also triggers on \"tell <repo>\", \"message <repo>\", \"ask <repo>\", \"send <repo>\". Works for questions and statements alike. Messages travel via tmux named buffers — no network, no files."
argument-hint: "<send|read|peek|list> [repo] [message...]"
allowed-tools: Bash(bash:*)
---

Run the bundled script with the verb and any arguments forwarded verbatim:

```
bash "${CLAUDE_SKILL_DIR}/claude-msg" $ARGUMENTS
```

`${CLAUDE_SKILL_DIR}` resolves to this skill's own directory — the script is never looked up from `$PATH`.

Verbs:

- `send <repo> <message...>` — deliver a message to `<repo>`'s inbox (e.g. `/msg send jarvis "are you done yet?"`)
- `read [repo]` — print and consume inbox; defaults to `basename $PWD` when repo is omitted (e.g. `/msg read`)
- `peek [repo]` — print inbox without consuming
- `list` — list all inboxes that have pending mail

After a `read` or `peek`, act on any messages received: answer questions, produce requested output, or note that the inbox was empty.
