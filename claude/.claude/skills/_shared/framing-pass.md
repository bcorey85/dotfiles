# Shared Framing Pass (single source of truth)

The user's design intent, stated **before the agent proposes anything**. Runs
in both planning lanes: `/eng-spec` Phase 2.5 and `/deep-plan` Phase D step 0.

## Why this exists

Without it, the agent picks what counts as a decision, generates the option
set, ranks it, and presents its favorite first. The user answers multiple
choice on an exam the agent wrote. Their acceptance is then recorded as if
they had designed it.

The evidence for the ordering, not just the existence, of this step:

- Working unaided first and adopting the model second preserves engagement and
  ownership; model-first participants reported the LOWEST ownership of their
  own output and could not reliably reproduce it minutes later (MIT Media Lab,
  Kosmyna et al. 2025 — the Brain-to-LLM vs LLM-to-Brain arms).
- Professional developers who use agents effectively keep design authority:
  9 of 11 observed wrote the design plan themselves; the survey's line falls
  at delegating the DECISION (0:12 on "replacing human expertise or decision
  making"), never at agent involvement in design — brainstorming and talking
  problems out score 11:5 and 6:0 net-suitable (arXiv 2512.14012).
- Reviewing the agent's proposal afterward is a weaker safeguard than it
  feels: automation bias occurs in experts and "cannot be prevented by
  training or instructions" (Parasuraman & Manzey 2010).

So the agent stays fully in the design conversation. It just stops going
first.

## The step

**Blocking. The agent writes nothing and proposes nothing until the user
answers.** Ask with AskUserQuestion (free-text "Other" is the expected path —
the options exist only to make the shape obvious), or plain prose if the
lane's flow suits it better. Three prompts:

1. **The approach you'd take** — one or two sentences, however rough. "I'd
   put it in the existing worker rather than a new service." Rough is the
   point; this is an anchor, not a design.
2. **The one thing it makes worse** — every real approach costs something. If
   nothing gets worse, the approach hasn't been thought about yet.
3. **What you're unsure about** — the fork you can't call. This is what the
   agent's exploration is FOR; naming it is what turns exploration into
   answering your question instead of framing it for you.

Six lines total is plenty. Two is fine. The value is in it existing before the
agent speaks, not in its polish.

## Escape hatch

Skip when the change is one the user "could describe the diff in one
sentence" (Anthropic's own bar for skipping planning entirely) — pure config,
a flag, a version bump. `/eng-spec`'s existing "go lean" path skips this step
along with the architect.

Do NOT skip it on routine-but-real work. That is precisely where the erosion
concentrates: critical engagement drops most "in routine or lower-stakes tasks
in which users simply rely on AI" (Lee et al., CHI 2025). The hard tickets
defend themselves — you would push back anyway. The boring ones are the ones
that get waved through.

## How the answer is used downstream

- It is passed to the architect / research phase **as the user's stated
  approach, to be validated or challenged — never silently replaced.** An
  architect that ignores the framing and returns its own unrelated design has
  failed the dispatch.
- It is the main — but NOT the only — input to the owner tags in
  `~/.claude/skills/_shared/design-decision-format.md`. A decision traceable to
  the framing is `(User-originated)`; so are others that never touch the framing
  at all. § Owner tags owns the tests and enumerates them. Read it and tag from
  there; this bullet is not a summary of it and must not be used as one.
- If the agent's exploration shows the framing is WRONG, it says so plainly
  and explains why. Being talked out of your own approach by evidence is the
  system working — that is a real decision, and it is still yours. Silent
  replacement is not.
