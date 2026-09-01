---
name: brief
description: Report a finished unit of work as a verdict plus the decision owed, with detail held back until asked. Use when reporting a phase completion, a review packet, a measurement result, a multi-agent outcome, or any status the user must act on. Triggers on "summarize", "progressive disclose", "too long", "stop spamming", "brief me", "/brief".
---

# Brief — verdict first, detail on request

A status report is not a transcript. The user reads it to decide one thing:
what to do next. Every line that does not move that decision is spam, no
matter how true it is.

Default to this shape for any completion report. It is not a compression pass
over a long report — write the short thing first and hold the rest.

---

## The shape

**Layer 0 — always emitted. Hard cap: 8 lines.**

1. **Verdict line.** What is now true, in system terms. Not what you did — what
   the system does. One line.
2. **The decision owed**, if any. One question, phrased so it can be answered
   with a word. If there is no decision, say what happens next instead.
3. **Blockers only.** A hook block, a red gate, a stop. Nothing that passed.
4. **Expansion menu.** One line naming what is available, not summarizing it.

**Layer 1 — only when the user asks for a menu item.** Then give that item in
full. Depth on request is not spam; depth unasked is.

---

## Rules

- **A green gate is one word, or absent.** "Gates green" beats six lines of
  command names and pass counts. Name a gate only when it failed, was skipped,
  or its result is the decision.
- **One ask at a time.** If two decisions are open, lead with the one that
  blocks the other and say the second exists. Two questions in one report get
  one answer and a re-ask.
- **Never paste an agent packet.** Sub-agent reports, review packets and tool
  output are inputs to your judgment, not deliverables. Relay the conclusion in
  your own words; the user cannot see them anyway.
- **File paths, not tours.** A path is clickable. A paragraph describing what is
  in the file is not.
- **Corrections you already made are Layer 1**, unless the user must act on one.
  Fixing a wrong number is work, not news.
- **No re-litigating settled scope.** A decision the user already made does not
  get re-explained back to them.
- **Numbers keep their units and uncertainty** even at Layer 0. Brevity drops
  words, never conclusions or confidence.

## What the menu looks like

Name the contents, do not preview them:

```
More: the read queue (6 files) · the measurement table · what I corrected · deferred items
```

Not: a heading per item with two lines under each. That is the long report with
extra steps.

## When Layer 0 is not enough

Expand without being asked ONLY for:

- A security or data-loss consequence the user cannot act on if unstated.
- An irreversible action about to happen.
- A number that contradicts something the user already believes.

Then expand that ONE thing, in two sentences, and keep the rest held back.

---

## Anti-pattern (the thing that triggers this skill)

A phase report that opens with a behavior delta, then a hook-block paragraph,
then a six-file annotated queue, then the ask, then a paragraph of green gate
evidence, then two corrections, then a not-a-defect note, then next steps. Every
item defensible; the whole thing unreadable. The ask — the only line requiring
the user — arrives seventh.

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

Governs completion and status reports. Not code comments, commit messages, ADRs,
specs, or any committed artifact — those keep their own structural conventions.
Composes with Caveman (which compresses wording); this skill decides what exists
at all.
