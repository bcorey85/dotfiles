---
name: go
description: Resume from the handoff file /stop wrote for this checkout and terminal, then continue with its first open item. User-invoked only.
disable-model-invocation: true
allowed-tools: [Bash, Read]
---

# Go — pick up where /stop left off

The path comes from the helper that `/stop` writes with:

```bash
bash ~/.claude/skills/stop/handoff-path        # this checkout, this terminal
bash ~/.claude/skills/stop/handoff-path list   # every handoff for this checkout, newest first
```

1. Run the helper. If the file exists, read it.
2. If it does not exist, run `list`. One file: read it. Several: show their paths and dates, then ask which. None: say so and stop.
3. Continue with the first item under **Not decided**, unless the arguments name another item.
4. When every item in the file is absorbed, delete the file with `rm`.

## Arguments

`$ARGUMENTS` names the item to take first.
