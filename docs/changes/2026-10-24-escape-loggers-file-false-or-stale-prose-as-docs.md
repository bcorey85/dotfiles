---
type: "Change"
change_type: "changed"
title: "Escape loggers file false or stale prose as docs"
description: "The four skills that log escapes by hand name the `docs` class, and the two that log review comments say a false or stale comment, doc or description is `docs`, never `smell` or `other`. The logger already accepted `docs`; the skills never offered it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T15:51:15-05:00"}
seq: 13
kind: "behavior"
components: ["skill/escape", "skill/cc", "skill/commit", "skill/pr-comments"]
evidence: ["census"]
watches: []
test: ""
unmeasured: "The before period has almost no docs escapes because the skills never offered the class, so a before-and-after watch on the class reads a false rise. Read it as a share: once about 40 new review escapes have landed, count the docs share of review escapes and compare it with the census share of false or stale prose."
---

## Change

- `skills/escape/SKILL.md`: the class list adds `docs`, with a one-line definition (prose false or stale about the code, even when the code is right).
- `skills/cc/SKILL.md`, `skills/commit/SKILL.md`, `skills/pr-comments/SKILL.md`: the `log-escape` command line lists `docs` among the classes.
- `skills/cc/SKILL.md`, `skills/pr-comments/SKILL.md`: one sentence says a comment that calls a comment, doc or description false or stale is `docs`, never `smell` or `other`.

## Evidence

Census of the review-gate escapes in the work logs. 46 of 355 were false or stale prose. The escape log filed 18 as `other`, 18 as `smell`, 10 as `bug`, and 1 as `docs`. The logger and the review-finding log have accepted `docs` since September, and the code reviewer logs its own prose findings as `docs`. Only the escape skills' class lists left it out, so the caught and escaped sides of the same defect did not cross-tabulate.

## Result

Pending. Predicted: most false or stale prose escapes log as `docs`, so the class carries about 13 percent of review escapes instead of under 1 percent.

## Watch

None. See `unmeasured`.

## Back-out

Remove `docs` from the four class lists and remove the `class:` sentence from `skills/cc/SKILL.md` and `skills/pr-comments/SKILL.md`.
