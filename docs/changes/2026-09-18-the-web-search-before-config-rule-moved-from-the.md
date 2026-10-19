---
type: "Change"
title: "The web-search-before-config rule moved from the global rules file to the main-session orchestration file"
description: "The web-search-before-config rule moved from the global rules file to the main-session orchestration file, and it now covers a dispatch as well as a direct write: the main session does the research and puts the result in the dispatch brief."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-18T00:00:00-05:00"}
seq: 9
components: ["rule/global-claude-md", "rule/orchestration"]
evidence: ["census", "judgment"]
watches: []
---

## Change

The web-search-before-config rule moved from the global rules file to the main-session orchestration file, and it now covers a dispatch as well as a direct write: the main session does the research and puts the result in the dispatch brief. The dependency skill points at the new home.

## Evidence

census, judgment

## Result

The global file loads into every subagent, and the writing agents hold no web tool, so the rule was a line that they paid for on every turn and had no way to obey. The writing agents made no web call in any recorded session. The rule costs about 70 tokens per turn, so the token gain is small. The gain is that the rule now sits with the one party that can act on it.

## Watch

—

## Back-out

—
