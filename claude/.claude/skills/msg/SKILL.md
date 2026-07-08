---
name: msg
description: 'Send or receive messages between Claude agents in separate repos'' tmux sessions (named buffers — no network, no files). Verbs: send <repo> <msg> | read [repo] | peek [repo] | list. Triggers on "check my inbox", "any messages", "tell <repo>", "message <repo>", "ask <repo>", "send <repo>". Verb details in the skill body.'
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
