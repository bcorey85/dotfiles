---
type: "Change"
title: "The toolkit health script now reports whether each deny-capable gate is actually registered"
description: "The toolkit health script now reports whether each deny-capable gate is actually registered, whether each standalone rules file is well-formed, and whether the session-start injection is wired up."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-12T00:00:00-05:00"}
seq: 12
components: ["script/claude-doctor"]
evidence: ["judgment"]
watches: []
---

## Change

The toolkit health script now reports whether each deny-capable gate is actually registered, whether each standalone rules file is well-formed, and whether the session-start injection is wired up.

## Evidence

judgment

## Result

Every mechanism in this group is silent when it is not running, and an unregistered gate looks exactly like a gate that found nothing — the failure mode the group as a whole is most exposed to. The checks extend the passes the script already makes over agent frontmatter and registrations rather than opening new ones.

## Watch

—

## Back-out

—
