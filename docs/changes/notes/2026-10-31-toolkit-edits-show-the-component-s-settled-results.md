---
type: "Change"
change_type: "added"
title: "Toolkit edits show the component's settled results first"
description: "A PreToolUse hook on Write, Edit and MultiEdit shows a component's settled results before the session's first edit of it, so a settled result is not retested or reversed by accident."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-31T14:52:39-05:00"}
seq: 1
kind: "user-rule"
components: ["script/settled-lessons-hook"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-31: the user added this hook's entry to settings.json themselves; the request came as a question, paraphrased: are results kept per component so they are not forgotten"
proof: []
unmeasured: "No intake number reads whether a session read a lesson."
---

## Change

Before the first edit of a toolkit component in a session, the hook adds that component's settled-results section as context. The component comes from the edited path (agent, shared skill file, skill, or any other file through the page's resource line). The hook adds context only, so every other gate still decides the edit, and it shows each component once per session. It stays silent when the results folder, page or section is missing.

## Evidence

Judgment, on a user question (paraphrased): are results kept per component so they are not forgotten. The user then registered the hook in `settings.json` themselves on 2026-10-31. The hook puts them in front of the editor at the moment of the edit.

## Result

An edit of a component with settled results starts with those results in context.

## Watch

None. No intake number reads whether a session read a lesson.

## Back-out

Delete the hook entry from `claude/.claude/settings.json` and the script `claude/.claude/scripts/gates/settled_lessons_hook.py`.
