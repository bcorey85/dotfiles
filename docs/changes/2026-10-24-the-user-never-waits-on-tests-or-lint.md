---
type: "Change"
title: "The user never waits on tests or lint"
description: "The global quality-checks block now says the agent runs the full suite and lint on the files an install command writes before it hands that command over, and the command only writes files."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T05:14:23-05:00"}
seq: 6
kind: "behavior"
components: ["agent/review-loop"]
evidence: ["user rule"]
watches: ["user-check-commands"]
test: ""
unmeasured: ""
---

## Change

- `CLAUDE.md`, `## Quality Checks`, new line: the user never waits on tests or lint. Before the agent hands over an install command, it runs the full suite and lint on the files that the command installs. It does not say done until they pass. The install command only writes files.

## Evidence

User rule. An install command that the agent handed over ran 712 tests for about 8 minutes after it copied the files. The agent then asked for a full suite run on top. Those tests had passed in the lane before the install.

## Result

The lane installers in the current fix batch now only back up and write files, and print the restore path.

## Watch

None. See `unmeasured`.

## Back-out

Remove the line from `## Quality Checks` in `CLAUDE.md`.
