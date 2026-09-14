---
name: brief
description: Report a finished unit of work as a verdict plus the decision owed, with detail held back until asked. Use when reporting a phase completion, a review packet, a measurement result, a multi-agent outcome, or any status the user must act on. Triggers on "summarize", "progressive disclose", "too long", "stop spamming", "brief me", "/brief".
---

# Brief — verdict first, detail on request

Every line that does not move the user's next decision is spam, no
matter how true it is.

Default for any completion report — write the short thing first, not a compression pass over a long one.

---

## The shape

**Layer 0 — always emitted. Hard cap: 8 lines.**

1. **Verdict.** What is now true, in system terms (not what you did). One line.
2. **Decision owed**, if any — one question answerable in a word; else what happens next.
3. **Blockers only.** A hook block, a red gate, a stop. Nothing that passed.
4. **Expansion menu.** One line naming what is available, not summarizing it.

**Layer 1 — only when the user asks for a menu item.** Then give that item in
full. Depth on request is not spam; depth unasked is.

---

## Rules

- **A green gate is one word or absent** — name gates only on failure, skip, or decision.
- **One ask at a time.** If two decisions are open, lead with the one that
  blocks the other and say the second exists.
- **Never paste an agent packet** — relay conclusions in your own words.
- **File paths, not tours.** A path is clickable. A paragraph describing what is
  in the file is not.
- **Your corrections are Layer 1** unless the user must act.
- **No re-litigating settled scope.**
- **Numbers keep their units and uncertainty** even at Layer 0. Brevity drops
  words, never conclusions or confidence.

## What the menu looks like

Name the contents, do not preview them:

```
More: the read queue (6 files) · the measurement table · what I corrected · deferred items
```

Not headings-with-previews — that is the long report with extra steps.

## When Layer 0 is not enough

Expand unasked ONLY for: unstated security or data-loss consequences; imminent irreversible actions; belief-contradicting numbers.
Then expand that ONE thing, in two sentences, and keep the rest held back.

---

## Anti-pattern (the thing that triggers this skill)

A phase report: behavior delta, hook-block paragraph, six-file queue, the ask, green-gate paragraph, two corrections, a not-a-defect note, next steps. Every item defensible; the ask arrives seventh.

Rewritten:

```
Phase 3 done: birthdates can no longer be mistaken for a date window, and age
questions use a real whole-year age figure. Gates green.

Blocked: /stage's classifier is hook-denied (false positive on the node call),
so nothing was staged — the queue is mine, not the classifier's.

Decision: `date_of_birth` is now a string with no `to_char` wrap, and the
rendering check needs VPN. Ship Phase 3 open, or check first?

More: the read queue (6 files) · gate evidence · what I corrected · Phase 4 scope
```

## Boundaries

Governs completion and status reports — not comments, commits, ADRs, specs.
This skill decides what exists at all, not how it is worded.
