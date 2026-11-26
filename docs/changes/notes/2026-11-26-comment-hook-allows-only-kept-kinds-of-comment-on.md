---
type: "Change"
change_type: "changed"
title: "Comment hook allows only kept kinds of comment on each edit"
description: "The comment-bloat-gate blocks each comment line an edit adds unless it is a license header, a lint or format suppression, a comment block on an exported or public symbol, or a line with a URL; the whole-file density cap is gone."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T12:37:05-06:00"}
seq: 18
kind: "user-rule"
components: ["script/comment-bloat-gate"]
evidence: ["user request"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: ""
---

## Change

The user asked for fewer comments, because the agents write too many. The gate used to block only when a whole file passed 22% comment lines, which still let through about one comment per four code lines. It now judges the comment lines each edit adds. An Edit adds the lines of `new_string` that neither `old_string` nor the committed file holds, inside the lines the edit wrote; a Write adds the lines the committed file lacks. Each added comment line is blocked unless it is a license header, a lint or format suppression, a comment block on an exported or public symbol, or a line with a URL. The deny lists each line as `number: text` and says to delete it or turn it into a name. Only whole comment lines count, never a trailing comment on a code line. Files under a `docs/` folder are not checked. The workflow-marker check is unchanged.

## Evidence

user request: the agents' comments were too many, and the density cap let them through.

## Result

Median run time over 41 runs: comment_bloat_gate 39.3 ms for an Edit with no comment and 46.0 ms for an Edit with a blocked comment, against a bare Python start of 7.8 ms.

Rule meter CG01 (sonnet coder writes a late-fee policy function with a test; one run per cell; the on arm runs this gate as a PostToolUse Write|Edit hook). Added comment lines, then lines that are no keep kind, per arm:

| Level | On: comment lines | On: unkept | Off: comment lines | Off: unkept |
|---|---|---|---|---|
| supportive | 2 | 0 | 4 | 2 |
| neutral | 6 | 0 | 6 | 4 |
| competing | 15 | 0 | 14 | 12 |

The on arm complied in 3 of 3 runs and the off arm in 0 of 3. In each on run the coder hit the block at least once and turned the comment into a name or deleted it.

## Watch

—

## Back-out

Restore the density cap in `comment_bloat_gate.py` from the commit before this change.
